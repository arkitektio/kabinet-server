"""Apps, flavours and repos carry a vector too, and every embedded row publishes it.

The string is `<model id>:<floats>`: a vector without the model that produced it is not
comparable to anything, so the descriptor travels inside the value rather than beside it.
"""

import uuid

import pytest
from asgiref.sync import sync_to_async
from kante.context import HttpContext

from bridge import models
from embeddings import engine
from embeddings.healer import reembed_stale
from embeddings.strawberry import format_embedding
from tests.utils import execute


@sync_to_async
def _catalogue(ctx: HttpContext) -> dict:
    """An app, a release, a flavour and a repo, as a scan would create them."""
    organization = ctx.request.organization
    app = models.App.objects.create(identifier="live.arkitekt.segmentation", organization=organization)
    release = models.Release.objects.create(app=app, version="0.1.0")
    image = models.DockerImage.objects.create(image_string="jhnnsrs/seg:0.1.0", organization=organization)
    repo = models.GithubRepo.objects.create(name="arkitektio-apps/ome:main", user="arkitektio-apps", repo="ome", branch="main", organization=organization)
    flavour = models.Flavour.objects.create(release=release, name="cuda", image=image, repo=repo, builder="arkitekt", manifest={"identifier": app.identifier, "author": "jhnnsrs"})
    return {"app": app, "flavour": flavour, "repo": repo}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_every_catalogue_row_embeds_on_save(authenticated_context: HttpContext) -> None:
    rows = await _catalogue(authenticated_context)

    for name, row in rows.items():
        await row.arefresh_from_db()
        assert row.embedding is not None and len(row.embedding) == 256, name
        assert row.embedding_model == engine.model_id(), name


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_flavour_embeds_the_app_it_was_built_from(authenticated_context: HttpContext) -> None:
    """A flavour named "cuda" is nothing on its own; the manifest is where its meaning is."""
    rows = await _catalogue(authenticated_context)
    flavour = rows["flavour"]

    assert await sync_to_async(flavour.embedding_source_text)() == "cuda\nlive.arkitekt.segmentation\njhnnsrs"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_the_field_carries_the_model_id_and_the_vector(authenticated_context: HttpContext) -> None:
    rows = await _catalogue(authenticated_context)
    repo = rows["repo"]
    await repo.arefresh_from_db()

    data = await execute("query { githubRepos { name embedding } }", authenticated_context)
    published = data["githubRepos"][0]["embedding"]

    model_id, _, floats = published.partition(":")
    assert model_id == engine.model_id()
    # The floats round-trip exactly, so a client can reuse the vector it was handed.
    assert [float(component) for component in floats.split(",")] == repo.embedding
    assert published == format_embedding(repo.embedding, engine.model_id())


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_an_unembedded_row_publishes_null(authenticated_context: HttpContext) -> None:
    definition = await models.Definition.objects.acreate(name="Nameless", hash=uuid.uuid4().hex, organization=authenticated_context.request.organization)
    await models.Definition.objects.filter(pk=definition.pk).aupdate(embedding=None, embedding_model="")

    data = await execute("query { definitions { embedding } }", authenticated_context)

    assert data["definitions"][0]["embedding"] is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_the_healer_re_embeds_every_new_model(authenticated_context: HttpContext) -> None:
    """The columns are on three more tables now; the sweep has to know about all of them."""
    rows = await _catalogue(authenticated_context)
    for row in rows.values():
        # `Repo` and not `GithubRepo`: the columns live on the base table.
        model = models.Repo if isinstance(row, models.GithubRepo) else type(row)
        await model.objects.filter(pk=row.pk).aupdate(embedding=None, embedding_model="some-older-model")
        assert await sync_to_async(reembed_stale)(model) == 1

    for row in rows.values():
        await row.arefresh_from_db()
        assert row.embedding is not None
        assert row.embedding_model == engine.model_id()
