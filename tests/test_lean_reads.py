"""Answers a list can ask for instead of fetching rows to count, group or filter them itself.

- `AppFilter.publisher`: one publisher's apps, exactly (`search` also matches action names and
  similar identifiers, so "more from this publisher" listed other publishers' apps).
- `AppOrder.runningCount`: the busiest apps first, past the first page.
- `App.releaseCount`, `GithubRepo.flavourCount` / `blokCount`: counts without the lists.
- `Definition.apps`: the apps that bring an action, once each, instead of every flavour.
- `RepoBlokFilter.search` also matches the repository's name.
- `Subscription.pods(resource:, backend:)`: one resource's pod events, not the organization's.
- A log dump announces its pod as updated, so a client waiting for logs need not poll.
"""

from dataclasses import dataclass

import pytest
from asgiref.sync import sync_to_async
from kante.context import HttpContext

from bridge import models
from tests.test_app_store import _app
from tests.test_pods import DUMP_LOGS, setup_pod
from tests.utils import execute

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]

APPS = "query($f: AppFilter, $o: [AppOrder!]! = []) { apps(filters: $f, ordering: $o) { identifier releaseCount runningCount } }"


async def _identifiers(ctx: HttpContext, filters: dict | None = None, ordering: list | None = None) -> list[str]:
    data = await execute(APPS, ctx, {"f": filters, "o": ordering or []})
    return [app["identifier"] for app in data["apps"]]


async def test_a_publishers_apps_and_no_one_elses(authenticated_context: HttpContext) -> None:
    await _app(authenticated_context, "live.arkitekt.segmentation")
    await _app(authenticated_context, "live.arkitekt.reporting")
    await _app(authenticated_context, "live.arkitekt.tools.viewer")  # publisher live.arkitekt.tools
    await _app(authenticated_context, "org.other.arkitekt-segmentation")
    await _app(authenticated_context, "live/arkitekt/napari")  # either separator

    mine = await _identifiers(authenticated_context, {"publisher": "live.arkitekt"})
    assert sorted(mine) == ["live.arkitekt.reporting", "live.arkitekt.segmentation", "live/arkitekt/napari"]

    assert await _identifiers(authenticated_context, {"publisher": "live.arkitekt.tools"}) == ["live.arkitekt.tools.viewer"]
    # A publisher is matched exactly, never as a pattern.
    assert await _identifiers(authenticated_context, {"publisher": "live.arkitek."}) == []
    assert await _identifiers(authenticated_context, {"publisher": "."}) == []


async def test_the_busiest_apps_first_and_release_counts(authenticated_context: HttpContext) -> None:
    await _app(authenticated_context, "live.arkitekt.idle", versions=("1.0.0", "1.1.0", "1.2.0"), deployments=("STOPPED",))
    await _app(authenticated_context, "live.arkitekt.busy", deployments=("RUNNING", "RUNNING"), released_days_ago=30)
    await _app(authenticated_context, "live.arkitekt.one", deployments=("RUNNING",), released_days_ago=10)

    data = await execute(APPS, authenticated_context, {"f": {"deployed": True}, "o": [{"runningCount": "DESC"}, {"releasedAt": "DESC"}]})

    assert [(a["identifier"], a["runningCount"]) for a in data["apps"]] == [("live.arkitekt.busy", 2), ("live.arkitekt.one", 1), ("live.arkitekt.idle", 0)]
    assert {a["identifier"]: a["releaseCount"] for a in data["apps"]}["live.arkitekt.idle"] == 3


async def test_a_definition_names_its_apps_once(authenticated_context: HttpContext, built_chain: dict) -> None:
    @sync_to_async
    def _second_release() -> str:
        """Another release of the same app declaring the same actions: its flavours are new, its app is not."""
        flavour = models.Flavour.objects.select_related("release__app", "image").get(id=built_chain["flavour_id"])
        release = models.Release.objects.create(app=flavour.release.app, version="99.0.0")
        copy = models.Flavour.objects.create(release=release, name="vanilla", image=flavour.image, builder=flavour.builder)
        copy.definitions.set(flavour.definitions.all())
        return flavour.release.app.identifier

    identifier = await _second_release()

    data = await execute("query { definitions { name flavours { id } apps { identifier } } }", authenticated_context)

    assert data["definitions"]
    for definition in data["definitions"]:
        assert len(definition["flavours"]) == 2
        assert definition["apps"] == [{"identifier": identifier}]


async def test_repository_counts_and_blok_search_by_repository(authenticated_context: HttpContext, built_chain: dict) -> None:
    @sync_to_async
    def _blok() -> int:
        repo = models.GithubRepo.objects.get(id=built_chain["repo_id"])
        models.RepoBlok.objects.create(repo=repo, organization=repo.organization, key="layers", name="Layer picker", source="<Blok/>")
        return models.Flavour.objects.filter(repo=repo).count()

    flavours = await _blok()

    data = await execute("query { githubRepos { name flavourCount blokCount } }", authenticated_context)
    assert data["githubRepos"] == [{"name": "ome", "flavourCount": flavours, "blokCount": 1}]

    found = await execute('query { repoBloks(filters: { search: "OME" }) { key } }', authenticated_context)
    assert found["repoBloks"] == [{"key": "layers"}]


@dataclass
class _Pod:
    resource_id: object
    backend_id: object


async def test_pod_events_narrowed_to_a_resource_or_backend() -> None:
    from bridge.subscriptions.pod import PodEvent, keeps

    on_one = PodEvent(update=_Pod(resource_id=1, backend_id=7))  # type: ignore[arg-type]
    assert keeps(on_one, None, None)
    assert keeps(on_one, "1", None) and not keeps(on_one, "2", None)
    assert keeps(on_one, None, "7") and not keeps(on_one, "1", "8")
    # A deletion names only an id: whoever held the pod drops it.
    assert keeps(PodEvent(delete="5"), "2", "8")  # type: ignore[arg-type]


async def test_a_log_dump_announces_its_pod(authenticated_context: HttpContext, flavour_id: str) -> None:
    from bridge import channels

    ids = await setup_pod(authenticated_context, flavour_id)
    sent: list[tuple[object, list[str] | None]] = []
    original = channels.pod_channel.broadcast
    channels.pod_channel.broadcast = lambda message, groups=None: sent.append((message, groups))
    try:
        await execute(DUMP_LOGS, authenticated_context, {"input": {"pod": ids["pod"]["id"], "logs": "hello"}})
    finally:
        channels.pod_channel.broadcast = original

    pod_id = int(ids["pod"]["id"])
    assert [message.update for message, _ in sent] == [pod_id]
    assert channels.pod_group(pod_id) in (sent[0][1] or [])
