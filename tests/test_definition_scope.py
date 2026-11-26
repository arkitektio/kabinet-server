"""`DefinitionFilter` / `DefinitionOrder` fields that follow rekuest's `ActionFilter` / `ActionOrder`.

`inCollection` takes a collection's name and `appIdentifier` an app's identifier, the strings
the menu holds, as rekuest's do; `name` is a plain lookup. `search` ranks as rekuest's does:
the name itself, then a name prefix, then other matches.
"""

import uuid

import pytest
from asgiref.sync import sync_to_async
from django.test import override_settings
from kante.context import HttpContext

from bridge import models
from tests.utils import execute

LISTED = "query($f: DefinitionFilter, $o: [DefinitionOrder!]){ definitions(filters: $f, ordering: $o){ name } }"


@sync_to_async
def _catalogue(ctx: HttpContext) -> None:
    organization = ctx.request.organization
    image = models.DockerImage.objects.create(
        image_string="jhnnsrs/any:1.0.0", organization=organization
    )

    def flavour(app_identifier: str) -> models.Flavour:
        app = models.App.objects.create(
            identifier=app_identifier, organization=organization
        )
        release = models.Release.objects.create(app=app, version="1.0.0")
        return models.Flavour.objects.create(
            release=release, name="vanilla", image=image, builder="arkitekt"
        )

    measure, segment = (
        flavour("live.arkitekt.measure"),
        flavour("live.arkitekt.segment"),
    )
    analysis = models.Collection.objects.create(
        name="Analysis", description="", organization=organization
    )
    io = models.Collection.objects.create(
        name="IO", description="", organization=organization
    )

    def definition(
        name: str, flavour: models.Flavour, *collections: models.Collection
    ) -> None:
        row = models.Definition.objects.create(
            name=name, hash=uuid.uuid4().hex, organization=organization
        )
        row.flavours.add(flavour)
        row.collections.add(*collections)

    definition("Measure area", measure, analysis)
    definition("Measure length", measure, analysis, io)
    definition("Segment cells", segment)


async def _names(
    ctx: HttpContext, filters: dict, ordering: list | None = None
) -> list[str]:
    data = await execute(LISTED, ctx, {"f": filters, "o": ordering or []})
    return [d["name"] for d in data["definitions"]]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_in_collection_and_app_identifier(
    authenticated_context: HttpContext,
) -> None:
    ctx = authenticated_context
    await _catalogue(ctx)

    assert sorted(await _names(ctx, {"inCollection": "Analysis"})) == [
        "Measure area",
        "Measure length",
    ]
    assert await _names(ctx, {"inCollection": "IO"}) == ["Measure length"]
    assert await _names(ctx, {"inCollection": "Nothing"}) == []

    assert await _names(ctx, {"appIdentifier": "live.arkitekt.segment"}) == [
        "Segment cells"
    ]
    # What the Run section sends as `exceptApp`.
    assert sorted(
        await _names(ctx, {"NOT": {"appIdentifier": "live.arkitekt.segment"}})
    ) == [
        "Measure area",
        "Measure length",
    ]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_name_is_a_lookup(authenticated_context: HttpContext) -> None:
    ctx = authenticated_context
    await _catalogue(ctx)
    assert await _names(ctx, {"name": {"exact": "Segment cells"}}) == ["Segment cells"]
    assert sorted(await _names(ctx, {"name": {"startsWith": "Measure"}})) == [
        "Measure area",
        "Measure length",
    ]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_ordering_by_app_and_collection(
    authenticated_context: HttpContext,
) -> None:
    ctx = authenticated_context
    await _catalogue(ctx)

    names = await _names(ctx, {}, [{"appIdentifier": "DESC"}, {"name": "ASC"}])
    assert names == ["Segment cells", "Measure area", "Measure length"]

    # A definition in no collection comes last, either way.
    assert (await _names(ctx, {}, [{"collection": "ASC"}]))[-1] == "Segment cells"
    assert (await _names(ctx, {}, [{"collection": "DESC"}]))[-1] == "Segment cells"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_deployed_ordering_keeps_the_search_ranking(
    authenticated_context: HttpContext,
) -> None:
    """Deployed first, each group still in the order the search ranked it."""
    ctx = authenticated_context
    await _catalogue(ctx)

    @sync_to_async
    def deploy(name: str) -> None:
        from authentikate.models import Client

        definition = models.Definition.objects.get(name=name)
        client, _ = Client.objects.get_or_create(client_id="deployer")
        backend = models.Backend.objects.create(
            organization=ctx.request.organization,
            user=ctx.request.user,
            client=client,
            name="mine",
            kind="docker",
        )
        models.Deployment.objects.create(
            flavour=definition.flavours.get(), backend=backend
        )

    await deploy("Segment cells")

    with override_settings(EMBEDDINGS={"ENABLED": False}):
        searched = await _names(ctx, {"search": "measure"})
        assert searched == ["Measure area", "Measure length"]
        names = await _names(ctx, {}, [{"deployed": "DESC"}])
        assert names[0] == "Segment cells"
        names = await _names(ctx, {}, [{"deployed": "ASC"}])
        assert names[-1] == "Segment cells"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_search_ranks_the_name_then_a_prefix_then_the_rest(
    authenticated_context: HttpContext,
) -> None:
    ctx = authenticated_context

    @sync_to_async
    def definition(name: str, description: str = "") -> None:
        models.Definition.objects.create(
            name=name,
            description=description,
            hash=uuid.uuid4().hex,
            organization=ctx.request.organization,
        )

    await definition("Fast threshold", "a threshold, quickly")
    await definition("Threshold image")
    await definition("Otsu", "threshold by otsu's method")
    await definition("Threshold")

    with override_settings(EMBEDDINGS={"ENABLED": False}):
        names = await _names(ctx, {"search": "threshold"})
    assert names[:2] == ["Threshold", "Threshold image"]
    assert set(names[2:]) == {"Fast threshold", "Otsu"}
