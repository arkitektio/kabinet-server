"""The data path an app page needs: `app(id:)`, `apps`, and releases narrowed to one app.

Before this, kabinet published neither an `app` nor an `apps` query and `ReleaseFilter`
could not name an app -- so a page showing one app's versions had to read *every* release
in the organization and group them client-side, which is wrong the moment a second page of
releases exists.
"""

import pytest
from asgiref.sync import sync_to_async
from kante.context import HttpContext

from bridge import models
from tests.utils import execute, execute_raw

APPS = "query($f: AppFilter){ apps(filters: $f){ id identifier } }"
APP_PAGE = """
query AppPage($id: ID!, $ordering: [ReleaseOrder!]! = []) {
    app(id: $id) {
        identifier
        releases(ordering: $ordering) { version flavours { name } }
    }
}
"""
RELEASES = "query($f: ReleaseFilter){ releases(filters: $f){ version app { identifier } } }"


@sync_to_async
def _app(ctx: HttpContext, identifier: str, versions: tuple[str, ...] = ()) -> models.App:
    organization = ctx.request.organization
    app = models.App.objects.create(identifier=identifier, organization=organization)
    for version in versions:
        release = models.Release.objects.create(app=app, version=version)
        image = models.DockerImage.objects.create(image_string=f"jhnnsrs/{app.id}:{version}", organization=organization)
        models.Flavour.objects.create(release=release, name="vanilla", image=image, builder="arkitekt")
    return app


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_apps_lists_and_filters(authenticated_context: HttpContext) -> None:
    await _app(authenticated_context, "live.arkitekt.segmentation")
    await _app(authenticated_context, "live.arkitekt.reporting")

    everything = await execute(APPS, authenticated_context, {"f": None})
    assert {a["identifier"] for a in everything["apps"]} == {"live.arkitekt.segmentation", "live.arkitekt.reporting"}

    narrowed = await execute(APPS, authenticated_context, {"f": {"search": "segmentation"}})
    assert [a["identifier"] for a in narrowed["apps"]] == ["live.arkitekt.segmentation"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_an_app_page_is_one_query(authenticated_context: HttpContext) -> None:
    """The whole point: identifier, versions and their flavours without touching other apps."""
    app = await _app(authenticated_context, "live.arkitekt.segmentation", ("0.9.0", "0.10.0"))
    await _app(authenticated_context, "live.arkitekt.reporting", ("1.0.0",))

    data = await execute(APP_PAGE, authenticated_context, {"id": str(app.id), "ordering": [{"releasedAt": "DESC"}]})

    assert data["app"]["identifier"] == "live.arkitekt.segmentation"
    # Newest first, which a lexicographic sort on `version` would get wrong ("0.10.0" < "0.9.0").
    assert [r["version"] for r in data["app"]["releases"]] == ["0.10.0", "0.9.0"]
    assert [f["name"] for f in data["app"]["releases"][0]["flavours"]] == ["vanilla"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_releases_can_be_narrowed_to_an_app(authenticated_context: HttpContext) -> None:
    app = await _app(authenticated_context, "live.arkitekt.segmentation", ("0.9.0", "0.10.0"))
    other = await _app(authenticated_context, "live.arkitekt.reporting", ("1.0.0",))

    by_id = await execute(RELEASES, authenticated_context, {"f": {"app": str(app.id)}})
    assert {r["version"] for r in by_id["releases"]} == {"0.9.0", "0.10.0"}

    by_ids = await execute(RELEASES, authenticated_context, {"f": {"apps": [str(app.id), str(other.id)]}})
    assert len(by_ids["releases"]) == 3

    by_identifier = await execute(RELEASES, authenticated_context, {"f": {"identifier": "reporting"}})
    assert [r["app"]["identifier"] for r in by_identifier["releases"]] == ["live.arkitekt.reporting"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_an_app_of_another_organization_is_not_readable(
    authenticated_context: HttpContext,
    other_org_context: HttpContext,
) -> None:
    """`app(id:)` goes through `get_for_org`, like every other single-row query."""
    foreign = await _app(other_org_context, "live.arkitekt.secret", ("1.0.0",))

    result = await execute_raw(APP_PAGE, authenticated_context, {"id": str(foreign.id)})

    assert result.errors, "another organization's app must not resolve"
    assert (await execute(APPS, authenticated_context, {"f": None}))["apps"] == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_release_filters_do_not_leak_across_organizations(
    authenticated_context: HttpContext,
    other_org_context: HttpContext,
) -> None:
    """Naming another org's app id in the filter must return nothing, not its releases."""
    foreign = await _app(other_org_context, "live.arkitekt.secret", ("1.0.0",))

    data = await execute(RELEASES, authenticated_context, {"f": {"app": str(foreign.id)}})

    assert data["releases"] == []
