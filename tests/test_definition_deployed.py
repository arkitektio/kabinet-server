"""`DefinitionFilter.alreadyDeployed`: what is left to install.

A definition is deployed in its organization once a flavour that provides it has a deployment
on one of that organization's backends. The install menu asks with `false`, so a definition
already running is offered under Run, not again under Installable.
"""

import uuid

import pytest
from asgiref.sync import sync_to_async
from authentikate.models import Client, Organization
from kante.context import HttpContext

from bridge import models
from tests.utils import execute

FILTERED = "query($f: DefinitionFilter){ definitions(filters: $f){ name } }"


@sync_to_async
def _catalogue(ctx: HttpContext) -> None:
    organization, user = ctx.request.organization, ctx.request.user
    app = models.App.objects.create(identifier="measure", organization=organization)
    release = models.Release.objects.create(app=app, version="1.0.0")
    image = models.DockerImage.objects.create(image_string="jhnnsrs/measure:1.0.0", organization=organization)
    vanilla = models.Flavour.objects.create(release=release, name="vanilla", image=image, builder="arkitekt")
    cuda = models.Flavour.objects.create(release=release, name="cuda", image=image, builder="arkitekt")
    elsewhere = models.Flavour.objects.create(release=release, name="elsewhere", image=image, builder="arkitekt")

    def definition(name: str, *flavours: models.Flavour) -> None:
        row = models.Definition.objects.create(name=name, hash=uuid.uuid4().hex, organization=organization)
        row.flavours.add(*flavours)

    definition("Deployed", vanilla, cuda)  # two flavours, one deployed: once, not twice
    definition("Not deployed", cuda)
    definition("Deployed in another organization", elsewhere)

    client, _ = Client.objects.get_or_create(client_id="deployer")
    mine = models.Backend.objects.create(organization=organization, user=user, client=client, name="mine", kind="docker")
    models.Deployment.objects.create(flavour=vanilla, backend=mine)

    other = Organization.objects.create(identifier=f"other-{uuid.uuid4().hex[:8]}")
    theirs = models.Backend.objects.create(organization=other, user=user, client=client, name="theirs", kind="docker")
    models.Deployment.objects.create(flavour=elsewhere, backend=theirs)


async def _names(ctx: HttpContext, filters: dict) -> list[str]:
    data = await execute(FILTERED, ctx, {"f": filters})
    return sorted(d["name"] for d in data["definitions"])


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_already_deployed_splits_the_catalogue(authenticated_context: HttpContext) -> None:
    """True keeps what runs in the organization (once each), false what is left to install."""
    await _catalogue(authenticated_context)

    assert await _names(authenticated_context, {"alreadyDeployed": True}) == ["Deployed"]
    assert await _names(authenticated_context, {"alreadyDeployed": False}) == ["Deployed in another organization", "Not deployed"]
