"""A guest of the organization, granted a collaboration and nothing else: what they read of kabinet, and
what they never do.

Their token lists their collaborations by key (`collabs`: lok's key, one across the hub). A full member
("test") puts an app in a collaboration under a fresh key: its releases and flavours are in it with it,
and their images and the actions they provide come along. Where the organization runs it (deployments,
pods, backends), who approved it, and its catalogs are never shared.
"""

import asyncio
import uuid

import pytest
from django.test import AsyncClient
from kante.context import HttpContext
from strawberry.types import ExecutionResult

from bridge import models
from kabinet_server.schema import schema
from tests.conftest import GuestFactory, token_context
from tests.sharing import (
    collaboration,
    deploy,
    ids,
    member,
    provide,
    push,
    refused,
    run,
)

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]

LISTS = """
{
  apps { id }
  releases { id }
  flavours { id }
  definitions { id }
  deployments { id }
  pods { id }
  backends { id }
  releaseApprovals { id }
  githubRepos { id }
}
"""
RENDER = """
query ($id: ID!) {
  app(id: $id) {
    id
    deploymentCount
    runningCount
    releases {
      id
      approvals { id }
      flavours { id image { imageString } definitions { id name } deployments { id } }
    }
  }
}
"""
APP = "query ($id: ID!) { app(id: $id) { id } }"
DEPLOYMENT = "query ($id: ID!) { deployment(id: $id) { id } }"
ADD = "mutation ($input: CollaborationObjectInput!) { addToCollaboration(input: $input) { key } }"


async def _guest(
    ctx: HttpContext, query: str, **variables: object
) -> dict[str, object]:
    result = await run(ctx, query, **variables)
    assert not result.errors, result.errors
    assert result.data is not None
    return result.data


async def test_a_guest_reads_the_shared_app_and_nothing_of_where_it_runs(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    other = await push("live.arkitekt.other", "1.0")  # the oldest: first on a page
    shared = await push("live.arkitekt.shared", "1.0")
    action = await provide(authenticated_context, shared.flavour, "segment")
    unrelated = await provide(authenticated_context, other.flavour, "unrelated")
    running = await deploy(authenticated_context, shared.flavour)
    ctx = guest(
        {
            await collaboration(
                authenticated_context, ("@kabinet/app", shared.app.pk)
            ): []
        }
    )

    seen = await _guest(ctx, LISTS)

    assert ids(seen, "apps") == {str(shared.app.pk)}
    assert ids(seen, "releases") == {str(shared.release.pk)}
    assert ids(seen, "flavours") == {str(shared.flavour.pk)}
    assert ids(seen, "definitions") == {str(action.pk)}, (
        f"the action its flavour provides comes along, not {unrelated.pk}"
    )
    for never in ("deployments", "pods", "backends", "releaseApprovals", "githubRepos"):
        assert seen[never] == [], never
    first = await _guest(ctx, "{ apps(pagination: {limit: 1}) { id } }")
    assert ids(first, "apps") == {str(shared.app.pk)}, "narrowed before the page is cut"

    rendered = await _guest(ctx, RENDER, id=str(shared.app.pk))
    app = rendered["app"]
    assert isinstance(app, dict)
    [release] = app["releases"]
    assert release["approvals"] == [], "who approved it is never a guest's"
    [flavour] = release["flavours"]
    assert flavour["image"] == {
        "imageString": "registry.example/live.arkitekt.shared:1.0"
    }, "the image it deploys comes along"
    assert [d["id"] for d in flavour["definitions"]] == [str(action.pk)]
    assert flavour["deployments"] == [], "where it runs is never a guest's"
    assert (app["deploymentCount"], app["runningCount"]) == (0, 0), (
        "nor how often it runs"
    )

    assert (await run(ctx, APP, id=str(other.app.pk))).errors
    assert (await run(ctx, DEPLOYMENT, id=str(running.deployment.pk))).errors
    member_sees = await member(LISTS)
    assert ids(member_sees, "deployments") == {str(running.deployment.pk)}, (
        "a full member is not narrowed"
    )
    counted = await member(
        "query ($id: ID!) { app(id: $id) { deploymentCount } }", id=str(shared.app.pk)
    )
    assert counted["app"] == {"deploymentCount": 1}


async def test_what_a_shared_app_gains_later_comes_along(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    first = await push("live.arkitekt.growing", "1.0")
    key = await collaboration(authenticated_context, ("@kabinet/app", first.app.pk))

    second = await push("live.arkitekt.growing", "2.0")
    action = await provide(authenticated_context, second.flavour, "added later")

    seen = await _guest(guest({key: []}), RENDER, id=str(first.app.pk))
    app = seen["app"]
    assert isinstance(app, dict)
    flavours = {
        flavour["id"]: flavour
        for release in app["releases"]
        for flavour in release["flavours"]
    }
    assert set(flavours) == {str(first.flavour.pk), str(second.flavour.pk)}
    assert flavours[str(second.flavour.pk)]["image"] == {
        "imageString": "registry.example/live.arkitekt.growing:2.0"
    }, "a new flavour brings its image"
    assert [d["id"] for d in flavours[str(second.flavour.pk)]["definitions"]] == [
        str(action.pk)
    ], "an action provided later comes along"


async def test_what_is_never_shared_cannot_be_put_in(
    authenticated_context: HttpContext,
) -> None:
    shared = await push("live.arkitekt.shared", "1.0")
    running = await deploy(authenticated_context, shared.flavour)
    catalog = await models.Catalog.objects.acreate(
        organization=authenticated_context.request.organization,
        url="https://example.org/catalog.yaml",
        name="Ours",
    )
    key = await collaboration(authenticated_context, ("@kabinet/app", shared.app.pk))

    for identifier, pk in (
        ("@kabinet/deployment", running.deployment.pk),
        ("@kabinet/pod", running.pod.pk),
        ("@kabinet/catalog", catalog.pk),
    ):
        tried = await run(
            token_context("test"),
            ADD,
            input={"collaboration": key, "identifier": identifier, "object": str(pk)},
        )
        assert tried.errors, f"{identifier} {pk} was put in a collaboration"


async def test_a_guest_writes_nothing_and_shares_nothing(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    shared = await push("live.arkitekt.shared", "1.0")
    key = await collaboration(authenticated_context, ("@kabinet/app", shared.app.pk))
    ctx = guest({key: ["kabinet_deployer", "kabinet_approver"]})

    attempts = {
        "a deployment": (
            'mutation ($flavour: ID!) { createDeployment(input: {flavour: $flavour, localId: "x"}) { id } }',
            {"flavour": str(shared.flavour.pk)},
        ),
        "an approval": (
            'mutation ($release: ID!) { approveRelease(input: {release: $release, mandate: "m", agent: "a"}) { id } }',
            {"release": str(shared.release.pk)},
        ),
        "a backend": (
            'mutation { declareBackend(input: {instanceId: "x", kind: "docker", name: "n"}) { id } }',
            {},
        ),
        "a share": (
            ADD,
            {
                "input": {
                    "collaboration": key,
                    "identifier": "@kabinet/app",
                    "object": str(shared.app.pk),
                }
            },
        ),
    }
    for what, (mutation, variables) in attempts.items():
        result = await run(ctx, mutation, **variables)
        assert result.errors, f"{what} was let through"
        refused(result, "SCOPED_READ_ONLY")


async def test_root_fields_that_hand_out_no_apps_are_closed_to_a_guest(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    shared = await push("live.arkitekt.shared", "1.0")
    key = await collaboration(authenticated_context, ("@kabinet/app", shared.app.pk))
    other = await push("live.arkitekt.theirs", "1.0")
    await collaboration(authenticated_context, ("@kabinet/app", other.app.pk))
    ctx = guest({key: []})

    for closed in (
        "{ collaborationsStats { count } }",
        "{ appStoreTotals { apps } }",
        "{ githubRepoStats { count } }",
    ):
        refused(await run(ctx, closed), "COLLABORATION_DOES_NOT_REACH")
    listed = await _guest(ctx, "{ collaborations { key } }")
    assert listed["collaborations"] == [{"key": key}], "only the ones granted to them"
    blok = await _guest(
        ctx,
        "query ($id: ID!) { flavourBlok(id: $id) { id } }",
        id=f"{other.flavour.pk}:logo",
    )
    assert blok["flavourBlok"] is None, "a blok of an unshared flavour is not found"


async def test_a_guest_listing_catalogs_sees_none_and_writes_none(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    await models.Catalog.objects.acreate(
        organization=authenticated_context.request.organization,
        url="https://example.org/catalog.yaml",
        name="Ours",
    )
    shared = await push("live.arkitekt.shared", "1.0")
    ctx = guest(
        {
            await collaboration(
                authenticated_context, ("@kabinet/app", shared.app.pk)
            ): []
        }
    )
    before = await models.Catalog.objects.acount()

    seen = await _guest(ctx, "{ catalogs { id } catalogEntries { id } }")

    assert seen == {"catalogs": [], "catalogEntries": []}
    assert await models.Catalog.objects.acount() == before


async def test_a_guest_is_refused_the_pod_stream(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    """A subscription streams the organization's events, which no queryset narrows (the WebSocket transport)."""
    shared = await push("live.arkitekt.shared", "1.0")
    key = await collaboration(authenticated_context, ("@kabinet/app", shared.app.pk))

    stream = await schema.subscribe(
        "subscription { pods { create { id } } }", context_value=guest({key: []})
    )
    if not isinstance(stream, ExecutionResult):
        # Over a WebSocket the refusal is the stream's first (and only) message.
        stream = await asyncio.wait_for(anext(stream), timeout=5)
    refused(stream, "SCOPED_READ_ONLY")


async def test_the_routes_beside_graphql_take_no_guest_token(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    """The service manifest and the hook agent are signed by rekuest, never by a bearer token."""
    guest({str(uuid.uuid4()): []})

    for route, method in (
        ("/_rekuest/service/manifest", "get"),
        ("/_rekuest/hook", "post"),
        ("/_rekuest/hook/manifest", "get"),
    ):
        client = AsyncClient()
        response = await getattr(client, method)(
            route, headers={"Authorization": "Bearer guest"}
        )
        assert response.status_code in (401, 403, 405, 503), (
            route,
            response.status_code,
        )
