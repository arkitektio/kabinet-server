"""Sharing a workflow: what a root task created in kabinet, put in a collaboration as it is now.

A workflow is a root task (koherent's ``Task.root_task_id``). An app, a release, a flavour, an action
definition and a repository record the task they were created through (``created_through``): an app
image pushed under the provenance token an agent sends (``createAppImage`` with the ``Rekuest-Task``
header, signed by the test rekuest key in ``tests/fixtures/provenance_key.json``) stamps its app,
release and flavour. Deployments, pods and catalogs are never shared, so no workflow share puts them
in, and no structure is ``unknown``.
"""

import uuid
from dataclasses import dataclass

import pytest
from arkitekt_service.collaborations.models import Collaboration, CollaborationItem
from asgiref.sync import sync_to_async
from kante.context import HttpContext
from koherent.models import Task

from bridge import models
from tests.conftest import GuestFactory, token_context
from tests.sharing import (
    GraphQLData,
    Pushed,
    Running,
    deploy,
    ids,
    member,
    provide,
    push,
    run,
    task_token,
)

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]

SHARE = """
mutation ($input: ShareWorkflowInput!) {
  shareWorkflow(input: $input) {
    collaboration
    dryRun
    added { identifier object }
    covered
    skipped { identifier object wholeIdentifier whole }
    unknown
  }
}
"""
ADD = "mutation ($input: CollaborationObjectInput!) { addToCollaboration(input: $input) { key } }"
LISTS = """
query ($apps: AppFilter, $releases: ReleaseFilter, $flavours: FlavourFilter, $definitions: DefinitionFilter, $deployments: DeploymentFilter, $repos: GithubRepoFilter) {
  apps(filters: $apps) { id }
  releases(filters: $releases) { id }
  flavours(filters: $flavours) { id }
  definitions(filters: $definitions) { id }
  deployments(filters: $deployments) { id }
  githubRepos(filters: $repos) { id }
}
"""
EMPTY = {
    "apps": [],
    "releases": [],
    "flavours": [],
    "definitions": [],
    "deployments": [],
    "githubRepos": [],
}


@dataclass(frozen=True)
class Workflow:
    """A workflow's root task and what it made, beside what it did not."""

    root: str
    made: Pushed
    action: models.Definition
    repo: models.GithubRepo
    #: Made before the workflow, and not shared; the workflow pushed a new release of it.
    older: Pushed
    later: Pushed
    #: Made in the organization without a provenance token.
    unrelated: Pushed
    #: Where the workflow's app runs: never shared.
    running: Running


@sync_to_async
def _creating_task(app: models.App) -> Task:
    task = (
        models.App.objects.select_related("created_through")
        .get(pk=app.pk)
        .created_through
    )
    assert task is not None, "the app records no task"
    return task


async def _workflow(ctx: HttpContext) -> Workflow:
    """A workflow (two tasks under one root) that pushed a new app and a new release of an older
    one, and made an action and a repository; plus an app it did not make, and where its app runs."""
    older = await push("live.arkitekt.older", "1.0")
    unrelated = await push("live.arkitekt.unrelated", "1.0")
    root = f"root-{uuid.uuid4().hex}"
    made = await push(
        "live.arkitekt.made", "1.0", task=task_token(f"task-{uuid.uuid4().hex}", root)
    )
    later = await push(
        "live.arkitekt.older", "2.0", task=task_token(f"task-{uuid.uuid4().hex}", root)
    )
    task = await _creating_task(made.app)
    action = await provide(ctx, made.flavour, "segment", created_through=task)
    repo = await models.GithubRepo.objects.acreate(
        name="made",
        organization=ctx.request.organization,
        repo="made",
        user="arkitektio-apps",
        branch="main",
        created_through=task,
    )
    running = await deploy(ctx, made.flavour)
    return Workflow(
        root=root,
        made=made,
        action=action,
        repo=repo,
        older=older,
        later=later,
        unrelated=unrelated,
        running=running,
    )


def _sorted(share: object) -> GraphQLData:
    assert isinstance(share, dict)
    return {
        **share,
        "added": sorted(share["added"], key=lambda a: (a["identifier"], a["object"])),
    }


def _report(workflow: Workflow, key: str, *, dry_run: bool) -> GraphQLData:
    """What sharing ``workflow`` reports: its app, action and repository put in, the app's release
    and flavour covered by it, the new release of the older app (and its flavour) left out."""
    return {
        "collaboration": key,
        "dryRun": dry_run,
        "added": [
            {"identifier": "@kabinet/app", "object": str(workflow.made.app.pk)},
            {"identifier": "@kabinet/definition", "object": str(workflow.action.pk)},
            {"identifier": "@kabinet/githubrepo", "object": str(workflow.repo.pk)},
        ],
        "covered": 2,
        "skipped": [
            {
                "identifier": "@kabinet/release",
                "object": str(workflow.later.release.pk),
                "wholeIdentifier": "@kabinet/app",
                "whole": str(workflow.older.app.pk),
            },
            {
                "identifier": "@kabinet/flavour",
                "object": str(workflow.later.flavour.pk),
                "wholeIdentifier": "@kabinet/release",
                "whole": str(workflow.later.release.pk),
            },
        ],
        "unknown": [],
    }


async def test_an_app_image_pushed_in_a_workflow_records_the_task_it_was_created_through(
    authenticated_context: HttpContext,
) -> None:
    workflow = await _workflow(authenticated_context)

    @sync_to_async
    def roots() -> dict[str, str | None]:
        def root_of(
            model: type[models.App | models.Release | models.Flavour], pk: int
        ) -> str | None:
            task = (
                model.objects.select_related("created_through")
                .get(pk=pk)
                .created_through
            )
            return task.root_task_id if task is not None else None

        return {
            "app": root_of(models.App, workflow.made.app.pk),
            "release": root_of(models.Release, workflow.made.release.pk),
            "flavour": root_of(models.Flavour, workflow.made.flavour.pk),
            "new release of the older app": root_of(
                models.Release, workflow.later.release.pk
            ),
            "older app": root_of(models.App, workflow.older.app.pk),
            "unrelated app": root_of(models.App, workflow.unrelated.app.pk),
        }

    assert await roots() == {
        "app": workflow.root,
        "release": workflow.root,
        "flavour": workflow.root,
        "new release of the older app": workflow.root,
        "older app": None,  # found by the upsert, not created: left as it was
        "unrelated app": None,
    }


async def test_a_dry_run_says_what_sharing_a_workflow_puts_in_and_writes_nothing(
    authenticated_context: HttpContext,
) -> None:
    workflow = await _workflow(authenticated_context)
    key = str(uuid.uuid4())

    tried = await member(
        SHARE, input={"collaboration": key, "rootTask": workflow.root, "dryRun": True}
    )

    assert _sorted(tried["shareWorkflow"]) == _report(workflow, key, dry_run=True)
    assert not await Collaboration.objects.filter(key=key).aexists()
    assert await CollaborationItem.objects.acount() == 0


async def test_sharing_a_workflow_puts_in_what_it_made_and_a_guest_sees_exactly_that(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    workflow = await _workflow(authenticated_context)
    key = str(uuid.uuid4())
    before = await run(guest({key: []}), LISTS)
    assert not before.errors, before.errors
    assert before.data == EMPTY, (
        "a key granted before anything is put in here holds nothing"
    )

    shared = await member(
        SHARE, input={"collaboration": key, "rootTask": workflow.root, "name": "Pilot"}
    )

    assert _sorted(shared["shareWorkflow"]) == _report(workflow, key, dry_run=False)
    assert (await Collaboration.objects.aget(key=key)).name == "Pilot"
    seen = await run(guest({key: []}), LISTS)
    assert not seen.errors, seen.errors
    assert seen.data is not None
    assert ids(seen.data, "apps") == {str(workflow.made.app.pk)}
    assert ids(seen.data, "releases") == {str(workflow.made.release.pk)}, (
        "not the new release of the older app"
    )
    assert ids(seen.data, "flavours") == {str(workflow.made.flavour.pk)}
    assert ids(seen.data, "definitions") == {str(workflow.action.pk)}
    assert ids(seen.data, "githubRepos") == {str(workflow.repo.pk)}
    assert seen.data["deployments"] == [], "where it runs is never shared"

    stranger = await run(guest({str(uuid.uuid4()): []}), LISTS)
    assert stranger.data == EMPTY, "another key sees nothing of it"


async def test_a_release_of_an_older_app_comes_along_once_that_app_is_shared(
    authenticated_context: HttpContext, guest: GuestFactory
) -> None:
    workflow = await _workflow(authenticated_context)
    key = str(uuid.uuid4())
    await member(SHARE, input={"collaboration": key, "rootTask": workflow.root})

    await member(
        ADD,
        input={
            "collaboration": key,
            "identifier": "@kabinet/app",
            "object": str(workflow.older.app.pk),
        },
    )
    again = await member(SHARE, input={"collaboration": key, "rootTask": workflow.root})

    report = again["shareWorkflow"]
    assert isinstance(report, dict)
    assert report["skipped"] == []
    assert report["covered"] == 4, "both releases and their flavours, with their apps"
    seen = await run(guest({key: []}), LISTS)
    assert seen.data is not None
    assert ids(seen.data, "releases") == {
        str(workflow.made.release.pk),
        str(workflow.older.release.pk),
        str(workflow.later.release.pk),
    }


async def test_lists_filter_by_the_workflow_that_made_them_and_by_collaboration(
    authenticated_context: HttpContext,
) -> None:
    workflow = await _workflow(authenticated_context)
    key = str(uuid.uuid4())
    under = {"createdUnder": workflow.root}

    made = await member(
        LISTS,
        apps=under,
        releases=under,
        flavours=under,
        definitions=under,
        deployments=under,
        repos=under,
    )

    assert ids(made, "apps") == {str(workflow.made.app.pk)}
    assert ids(made, "releases") == {
        str(workflow.made.release.pk),
        str(workflow.later.release.pk),
    }
    assert ids(made, "flavours") == {
        str(workflow.made.flavour.pk),
        str(workflow.later.flavour.pk),
    }
    assert ids(made, "definitions") == {str(workflow.action.pk)}
    assert ids(made, "githubRepos") == {str(workflow.repo.pk)}
    assert made["deployments"] == [], "a deployment is never a workflow's to share"

    inside = {"inCollaboration": key}
    nothing_yet = await member(LISTS, apps=inside, releases=inside, definitions=inside)
    assert all(nothing_yet[f] == [] for f in ("apps", "releases", "definitions"))

    await member(SHARE, input={"collaboration": key, "rootTask": workflow.root})
    shared = await member(
        LISTS, apps=inside, releases=inside, definitions=inside, deployments=inside
    )

    assert ids(shared, "apps") == {str(workflow.made.app.pk)}
    assert ids(shared, "releases") == {str(workflow.made.release.pk)}, (
        "a part of what was put in is in it, live"
    )
    assert ids(shared, "definitions") == {str(workflow.action.pk)}
    assert shared["deployments"] == []
    both = await member(
        LISTS,
        apps={"createdUnder": workflow.root, "inCollaboration": key},
        releases={"inCollaboration": key, "createdUnder": workflow.root},
    )
    assert ids(both, "apps") == {str(workflow.made.app.pk)}
    assert ids(both, "releases") == {str(workflow.made.release.pk)}


async def test_another_organization_shares_nothing_of_this_workflow(
    authenticated_context: HttpContext,
) -> None:
    workflow = await _workflow(authenticated_context)

    tried = await run(
        token_context("othertest"),
        SHARE,
        input={
            "collaboration": str(uuid.uuid4()),
            "rootTask": workflow.root,
            "dryRun": True,
        },
    )

    assert not tried.errors, tried.errors
    assert tried.data is not None
    report = tried.data["shareWorkflow"]
    assert report["added"] == [] and report["skipped"] == []


async def test_what_is_never_shared_stays_out_of_a_shared_workflow(
    authenticated_context: HttpContext,
) -> None:
    """A deployment, its pod, the backend and the approval behind it, the image's secrets: none of
    it is in the collaboration, put in or part of what was."""
    workflow = await _workflow(authenticated_context)
    key = str(uuid.uuid4())

    await member(SHARE, input={"collaboration": key, "rootTask": workflow.root})

    held = {
        model
        async for model in CollaborationItem.objects.filter(
            collaboration__key=key
        ).values_list("content_type__model", flat=True)
    }
    assert held == {"app", "definition", "githubrepo", "dockerimage"}, held
    inside = {"inCollaboration": key}
    listed = await member(
        "query ($d: DeploymentFilter, $p: PodFilter) { deployments(filters: $d) { id } pods(filters: $p) { id } }",
        d=inside,
        p=inside,
    )
    assert listed == {"deployments": [], "pods": []}
