"""The app store answered per app by the server, not folded together from every release.

Before this the store fetched every release with its flavours and deployments (unpaginated),
grouped them into apps and worked out "installed", "running", hardware and services on the
client. Now `apps` filters, orders and counts those facts itself, so a page of apps is right
past the first page.
"""

import datetime
import uuid

import pytest
from asgiref.sync import sync_to_async
from authentikate.models import Client, User
from django.utils import timezone
from kante.context import HttpContext

from bridge import models
from tests.utils import execute

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]

STORE = """
query($f: AppFilter, $o: [AppOrder!]! = [], $p: OffsetPaginationInput) {
    apps(filters: $f, ordering: $o, pagination: $p) {
        identifier
        latestRelease { version releasedAt }
        deploymentCount
        runningCount
        hardware
        accelerators
        services
    }
}
"""

CUDA = [{"kind": "cuda", "required": True}]


@sync_to_async
def _app(
    ctx: HttpContext,
    identifier: str,
    versions: tuple[str, ...] = ("1.0.0",),
    selectors: list[dict] | None = None,
    services: tuple[str, ...] = (),
    deployments: tuple[str, ...] = (),
    released_days_ago: int = 0,
) -> models.App:
    """An app with releases (the last one newest), one flavour each, and deployments of the newest flavour."""
    organization, user = ctx.request.organization, ctx.request.user
    app = models.App.objects.create(identifier=identifier, organization=organization)
    flavour = None
    for index, version in enumerate(versions):
        release = models.Release.objects.create(app=app, version=version)
        # `released_at` is auto_now_add: set it after the fact, oldest version first.
        models.Release.objects.filter(id=release.id).update(released_at=timezone.now() - datetime.timedelta(days=released_days_ago, hours=len(versions) - index))
        image = models.DockerImage.objects.create(image_string=f"jhnnsrs/{identifier}:{version}", organization=organization)
        flavour = models.Flavour.objects.create(
            release=release,
            name="vanilla",
            image=image,
            builder="arkitekt",
            selectors=selectors or [],
            requirements=[{"key": service, "service": service} for service in services],
        )
    if deployments:
        client, _ = Client.objects.get_or_create(client_id="deployer")
        backend, _ = models.Backend.objects.get_or_create(organization=organization, user=user, client=client, name="docker", kind="docker")
        for status in deployments:
            models.Deployment.objects.create(flavour=flavour, backend=backend, status=status)
    return app


async def _store(ctx: HttpContext, filters: dict | None = None, ordering: list | None = None, pagination: dict | None = None) -> list[dict]:
    data = await execute(STORE, ctx, {"f": filters, "o": ordering or [], "p": pagination})
    return data["apps"]


async def test_an_app_carries_its_store_facts(authenticated_context: HttpContext) -> None:
    await _app(
        authenticated_context,
        "live.arkitekt.segmentation",
        versions=("0.9.0", "0.10.0"),
        selectors=CUDA,
        services=("live.arkitekt.mikro", "live.arkitekt.rekuest"),
        deployments=("RUNNING", "RUNNING", "STOPPED"),
    )

    [app] = await _store(authenticated_context)
    assert app["identifier"] == "live.arkitekt.segmentation"
    # Newest by released_at, which a sort on `version` would get wrong.
    assert app["latestRelease"]["version"] == "0.10.0"
    assert app["deploymentCount"] == 3
    assert app["runningCount"] == 2
    assert app["hardware"] == ["GPU"]
    assert app["accelerators"] == ["cuda"]
    assert app["services"] == ["live.arkitekt.mikro", "live.arkitekt.rekuest"]


async def test_installed_hardware_and_service_filter_past_the_first_page(authenticated_context: HttpContext) -> None:
    # Many plain apps released recently; the one GPU, installed, mikro-needing app is the oldest.
    for index in range(4):
        await _app(authenticated_context, f"live.arkitekt.plain{index}", released_days_ago=index)
    await _app(
        authenticated_context,
        "live.arkitekt.gpu",
        selectors=CUDA,
        services=("live.arkitekt.mikro",),
        deployments=("PENDING",),
        released_days_ago=30,
    )

    newest_first = [{"releasedAt": "DESC"}]
    first_page = await _store(authenticated_context, ordering=newest_first, pagination={"limit": 2})
    assert [app["identifier"] for app in first_page] == ["live.arkitekt.plain0", "live.arkitekt.plain1"]

    for filters in ({"deployed": True}, {"hardware": ["GPU"]}, {"service": "live.arkitekt.mikro"}):
        found = await _store(authenticated_context, filters=filters, ordering=newest_first, pagination={"limit": 2})
        assert [app["identifier"] for app in found] == ["live.arkitekt.gpu"], filters

    not_installed = await _store(authenticated_context, filters={"deployed": False})
    assert len(not_installed) == 4
    on_cpu = await _store(authenticated_context, filters={"hardware": ["CPU"]})
    assert {app["identifier"] for app in on_cpu} == {f"live.arkitekt.plain{index}" for index in range(4)}
    assert all(app["hardware"] == ["CPU"] for app in on_cpu)

    oldest_first = await _store(authenticated_context, ordering=[{"releasedAt": "ASC"}], pagination={"limit": 1})
    assert [app["identifier"] for app in oldest_first] == ["live.arkitekt.gpu"]


async def test_an_app_by_its_exact_identifier(authenticated_context: HttpContext) -> None:
    await _app(authenticated_context, "live.arkitekt.segment")
    await _app(authenticated_context, "live.arkitekt.segmentation")

    exact = await _store(authenticated_context, filters={"identifier": "live.arkitekt.segment"})
    assert [app["identifier"] for app in exact] == ["live.arkitekt.segment"]
    several = await _store(authenticated_context, filters={"identifiers": ["live.arkitekt.segment", "live.arkitekt.segmentation"]})
    assert len(several) == 2


async def test_an_app_without_releases_has_no_facts(authenticated_context: HttpContext) -> None:
    await sync_to_async(models.App.objects.create)(identifier="live.arkitekt.empty", organization=authenticated_context.request.organization)
    [app] = await _store(authenticated_context)
    assert app == {
        "identifier": "live.arkitekt.empty",
        "latestRelease": None,
        "deploymentCount": 0,
        "runningCount": 0,
        "hardware": [],
        "accelerators": [],
        "services": [],
    }


async def test_one_app_reads_its_facts_without_the_list(authenticated_context: HttpContext) -> None:
    app = await _app(authenticated_context, "live.arkitekt.single", versions=("1.0.0", "2.0.0"), deployments=("RUNNING",))
    data = await execute(
        "query($id: ID!){ app(id: $id){ latestRelease { version } deploymentCount runningCount hardware services } }",
        authenticated_context,
        {"id": str(app.id)},
    )
    assert data["app"] == {"latestRelease": {"version": "2.0.0"}, "deploymentCount": 1, "runningCount": 1, "hardware": ["CPU"], "services": []}


@sync_to_async
def _brings(app: models.App, bloks: list[dict] | None = None, actions: tuple[str, ...] = (), release_index: int = -1) -> None:
    """Give one release's flavour (the newest by default) these declared bloks and actions."""
    releases = list(app.releases.order_by("released_at"))
    flavour = releases[release_index].flavours.get()
    if bloks is not None:
        models.Flavour.objects.filter(pk=flavour.pk).update(bloks=bloks)
    for name in actions:
        definition = models.Definition.objects.create(name=name, hash=uuid.uuid4().hex, organization=app.organization)
        definition.flavours.add(flavour)


def _blok(key: str, context: str = "PANEL", description: str = "") -> dict:
    return {"key": key, "context": context, "description": description}


async def test_apps_that_bring_bloks_and_what_a_search_names(authenticated_context: HttpContext) -> None:
    viewer = await _app(authenticated_context, "live.arkitekt.viewer", released_days_ago=3)
    await _brings(viewer, bloks=[_blok("volume_scene", "SCENE", "Look at a 3D stack"), _blok("logo", "LOGO")], actions=("Render Volume",))
    # Only a logo is no blok the store offers.
    logo_only = await _app(authenticated_context, "live.arkitekt.logoonly", released_days_ago=2)
    await _brings(logo_only, bloks=[_blok("logo", "LOGO", "a panel-free mark")])
    # Its newest release dropped the panel an older one brought: the store shows the newest.
    dropped = await _app(authenticated_context, "live.arkitekt.dropped", versions=("1.0.0", "2.0.0"), released_days_ago=1)
    await _brings(dropped, bloks=[_blok("old_panel")], actions=("Old Action",), release_index=0)
    for index in range(3):
        await _app(authenticated_context, f"live.arkitekt.plain{index}")

    newest_first = [{"releasedAt": "DESC"}]
    # Past a page full of apps without bloks.
    with_bloks = await _store(authenticated_context, filters={"bloks": True}, ordering=newest_first, pagination={"limit": 2})
    assert [app["identifier"] for app in with_bloks] == ["live.arkitekt.viewer"]
    assert len(await _store(authenticated_context, filters={"bloks": False})) == 5

    async def named(search: str) -> list[str]:
        return [app["identifier"] for app in await _store(authenticated_context, filters={"search": search})]

    assert "live.arkitekt.viewer" in await named("render vol")  # an action's name
    assert "live.arkitekt.viewer" in await named("VOLUME_SC")  # a scene's key
    assert "live.arkitekt.viewer" in await named("3d stack")  # a scene's description
    assert "live.arkitekt.dropped" not in await named("Old Action")  # an older release's action
    assert "live.arkitekt.dropped" not in await named("old_panel")
    assert "live.arkitekt.logoonly" not in await named("panel-free")  # a logo is not searched
    # Regex characters are taken as they are.
    assert await named('a(["\\') == []


async def test_store_totals_count_every_app_a_filter_keeps(authenticated_context: HttpContext, other_org_context: HttpContext) -> None:
    viewer = await _app(authenticated_context, "live.arkitekt.viewer", services=("live.arkitekt.mikro",), deployments=("RUNNING", "STOPPED"))
    await _brings(viewer, bloks=[_blok("scene", "SCENE")], actions=("Render", "Slice"))
    tracker = await _app(authenticated_context, "live.arkitekt.tracker", versions=("1.0.0", "2.0.0"), services=("live.arkitekt.mikro", "live.arkitekt.kraph"), deployments=("RUNNING",))
    await _brings(tracker, actions=("Track",))
    await _brings(tracker, actions=("Ancient",), release_index=0)
    await _app(authenticated_context, "live.arkitekt.plain")
    await _app(other_org_context, "live.arkitekt.theirs", services=("live.arkitekt.mikro",), deployments=("RUNNING",))

    totals = "query($f: AppFilter){ appStoreTotals(filters: $f){ apps actions flavours running services { service apps } } }"
    everything = (await execute(totals, authenticated_context, {"f": None}))["appStoreTotals"]
    assert everything == {
        "apps": 3,
        "actions": 3,  # the newest releases' actions, not the older release's
        "flavours": 3,
        "running": 2,
        "services": [{"service": "live.arkitekt.mikro", "apps": 2}, {"service": "live.arkitekt.kraph", "apps": 1}],
    }
    only_bloks = (await execute(totals, authenticated_context, {"f": {"bloks": True}}))["appStoreTotals"]
    assert only_bloks == {"apps": 1, "actions": 2, "flavours": 1, "running": 1, "services": [{"service": "live.arkitekt.mikro", "apps": 1}]}


# --- by member -------------------------------------------------------------------------------


@sync_to_async
def _member(sub: str) -> User:
    user, _ = User.objects.get_or_create(sub=sub, iss="static_issuer", defaults={"username": f"static_issuer_{sub}"})
    return user


async def test_repositories_and_approvals_by_member(authenticated_context: HttpContext) -> None:
    organization, me = authenticated_context.request.organization, authenticated_context.request.user
    other = await _member("42")

    @sync_to_async
    def _rows() -> tuple[str, str, str]:
        mine = models.GithubRepo.objects.create(name="mine", creator=me, organization=organization, repo="mine", user="gh-owner", branch="main")
        models.GithubRepo.objects.create(name="theirs", creator=other, organization=organization, repo="theirs", user="gh-owner", branch="main")
        oci = models.OciRepo.objects.create(name="ghcr.io/org/app", creator=other, organization=organization, registry="ghcr.io", repository="org/app")
        models.OciRepo.objects.create(name="ghcr.io/org/mine", creator=me, organization=organization, registry="ghcr.io", repository="org/mine")
        app = models.App.objects.create(identifier="live.arkitekt.approved", organization=organization)
        release = models.Release.objects.create(app=app, version="1.0.0")
        approval = models.ReleaseApproval.objects.create(release=release, organization=organization, approver=other, mandate_id="m", agent="deployer", digest="d")
        models.ReleaseApproval.objects.create(release=release, organization=organization, approver=me, mandate_id="m2", agent="deployer", digest="d")
        return str(mine.id), str(oci.id), str(approval.id)

    mine, oci, approval = await _rows()

    repos = await execute("query($f: GithubRepoFilter){ githubRepos(filters: $f){ id creator { sub } } }", authenticated_context, {"f": {"creator": "1"}})
    assert repos["githubRepos"] == [{"id": mine, "creator": {"sub": "1"}}]

    ocis = await execute("query($f: OciRepoFilter){ ociRepos(filters: $f, ordering: [{ addedAt: DESC }]){ id addedAt } }", authenticated_context, {"f": {"creator": "42"}})
    assert [row["id"] for row in ocis["ociRepos"]] == [oci]

    approvals = await execute("query($f: ReleaseApprovalFilter){ releaseApprovals(filters: $f){ id } }", authenticated_context, {"f": {"approver": "42", "revoked": False}})
    assert approvals["releaseApprovals"] == [{"id": approval}]
