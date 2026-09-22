"""`logo` and `originalLogo`, on a release and on its flavours.

`Flavour.logo` and `Flavour.originalLogo` were declared as model fields on the GraphQL
type, but those columns have only ever existed on `Release` -- so *selecting* either one
raised ``'Flavour' object has no attribute 'logo'`` for every client that asked, and no
test selected them. They read through to the release now, which is where a flavour's logo
comes from: a flavour is one build of a release.
"""

import pytest
from asgiref.sync import sync_to_async
from kante.context import HttpContext

from bridge import models
from tests.utils import execute

RELEASE_LOGOS = "query { releases { version logo originalLogo flavours { name logo originalLogo } } }"


@sync_to_async
def _release_with_logos(ctx: HttpContext, *, stored: bool) -> models.Release:
    """A release carrying an upstream logo URL, and optionally an ingested one."""
    organization = ctx.request.organization
    app = models.App.objects.create(identifier="live.arkitekt.logos", organization=organization)
    store = None
    if stored:
        store = models.MediaStore.objects.create(path="s3://media/logo.png", key="logo.png", bucket="media", organization=organization)
    release = models.Release.objects.create(app=app, version="0.1.0", original_logo="https://example.org/logo.png", logo=store)
    image = models.DockerImage.objects.create(image_string="jhnnsrs/logos:0.1.0", organization=organization)
    models.Flavour.objects.create(release=release, name="vanilla", image=image, builder="arkitekt")
    return release


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_flavour_reports_the_logos_of_its_release(authenticated_context: HttpContext) -> None:
    """The regression: selecting these on a flavour used to raise, not return null."""
    await _release_with_logos(authenticated_context, stored=False)

    release = (await execute(RELEASE_LOGOS, authenticated_context))["releases"][0]
    flavour = release["flavours"][0]

    assert release["originalLogo"] == "https://example.org/logo.png"
    assert flavour["originalLogo"] == release["originalLogo"]
    # Nothing has ingested the logo into the datalayer, so there is no stored one.
    assert release["logo"] is None
    assert flavour["logo"] is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_an_ingested_logo_comes_back_as_its_path(authenticated_context: HttpContext) -> None:
    """`Release.logo` is a `MediaStore` FK declared as a String: it must resolve to one.

    Every release in the wild has a null `logo`, which is why handing a `MediaStore` to a
    String field never blew up.
    """
    await _release_with_logos(authenticated_context, stored=True)

    release = (await execute(RELEASE_LOGOS, authenticated_context))["releases"][0]

    assert release["logo"] == "s3://media/logo.png"
    assert release["flavours"][0]["logo"] == "s3://media/logo.png"
