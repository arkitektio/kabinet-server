"""``descriptors`` on kabinet's types: what an object says about itself, from its structure's declaration.

One declaration (``kabinet_server.service``) feeds the manifest, the signals and this field, so the
tests hold the three to each other: the field answers what a signal about the object carries, in
the keys the manifest declares. The descriptors are stored, so a port's ``requires`` is a filter
on the list query. Every row here is written the way the catalogue writes it (``upsert_app_image``,
``apply_release``, the deployer's mutations), never by hand: a descriptor that only holds for a
row nobody writes says nothing. And the agent's sweep, which every organization schedules for
itself, touches that organization's rows only.
"""

import copy
import json

import pytest
import yaml
from asgiref.sync import sync_to_async
from authentikate.models import Organization
from django.core.management import call_command
from kante.context import HttpContext

from bridge import models
from bridge.repo.db import apply_release, upsert_app_image
from bridge.repo.models import AppImageInputModel, ReleaseDescriptorModel
from embeddings import engine
from embeddings.healer import stale_queryset
from kabinet_server.hook_agent import agent
from kabinet_server.service import service
from tests.test_pods import DECLARE_BACKEND, UPDATE_POD, setup_pod
from tests.test_signals import intake  # noqa: F401  the fixture
from tests.utils import build_relative_dir, execute, execute_raw

DESCRIBED = """
    query Described($flavour: ID!, $repo: ID!, $deployment: ID!, $pod: ID!) {
        flavour(id: $flavour) {
            descriptors
            release { descriptors app { descriptors } }
            definitions { descriptors }
        }
        githubRepo(id: $repo) { descriptors }
        deployment(id: $deployment) { descriptors }
        pod(id: $pod) { descriptors }
        flavours { id descriptors }
    }
"""

EMBEDDED = (models.Definition, models.App, models.Flavour, models.Repo)

#: What a GPU build states: a CUDA device with 8 GB, an arm64 CPU, 16 GB of memory, and a
#: preference for a node labelled fast (a preference, so no minimum is read off it).
CUDA_SELECTORS = [
    {"kind": "cuda", "computeCapability": "8.6", "memory": 8000},
    {"kind": "cpu", "arch": "arm64"},
    {"kind": "ram", "min": 16000},
    {"kind": "label", "key": "fast", "required": False, "weight": 5},
]
CUDA = {
    "@kabinet/flavour_name": "cuda",
    "@kabinet/selector_kinds": ["cpu", "cuda", "label", "ram"],
    "@kabinet/gpu": "cuda",
    "@kabinet/arch": ["arm64"],
    "@kabinet/min_ram_mb": 16000,
    "@kabinet/min_vram_mb": 8000,
}
VANILLA = {
    "@kabinet/flavour_name": "vanilla",
    "@kabinet/selector_kinds": [],
    "@kabinet/gpu": "none",
    "@kabinet/arch": [],
    "@kabinet/min_ram_mb": 0,
    "@kabinet/min_vram_mb": 0,
}
#: The one action of ``deployments.yaml``: Convert Omero, a function of a file and a stage.
CONVERT = {"@kabinet/kind": "FUNCTION", "@kabinet/pure": False, "@kabinet/idempotent": False, "@kabinet/n_args": 2, "@kabinet/n_returns": 1}


def _app_image(name: str, selectors: list[dict], digest: str) -> AppImageInputModel:
    """The app image of ``deployments.yaml``, built as the flavour ``name`` with these selectors."""
    with open(build_relative_dir("deployments/deployments.yaml")) as f:
        app_image = yaml.safe_load(f)["app_images"][0]
    return AppImageInputModel(**{**app_image, "flavourName": name, "selectors": selectors, "appImageId": digest})


def _catalogue(organization: Organization) -> dict[str, models.Flavour]:
    """A cuda and a vanilla flavour of one release of ``organization``, as a scan of their repository writes them."""
    repo = models.GithubRepo.objects.create(name="arkitektio-apps/ome:main", user="arkitektio-apps", repo="ome", branch="main", organization=organization)
    return {
        "cuda": upsert_app_image(_app_image("cuda", CUDA_SELECTORS, "c" * 64), organization, repo=repo),
        "vanilla": upsert_app_image(_app_image("vanilla", [], "v" * 64), organization, repo=repo),
    }


def _published(organization: Organization) -> dict[str, models.Release]:
    """A release proper and a channel's build of the app in ``release.json``, as an import of its OCI repository writes them."""
    repo = models.OciRepo.objects.create(name="ghcr.io/jhnnsrs/starmist", registry="ghcr.io", repository="jhnnsrs/starmist", channels=["main"], organization=organization)
    with open(build_relative_dir("deployments/release.json")) as f:
        descriptor = json.load(f)

    def release(version: str, channel: str | None) -> models.Release:
        said = copy.deepcopy(descriptor)
        said["manifest"]["version"], said["channel"] = version, channel
        return apply_release(ReleaseDescriptorModel(**said), repo, organization)

    return {"proper": release("0.1.0", None), "main": release("0.2.0-dev.abc1234", "main")}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_an_object_answers_the_descriptors_its_structure_declares(authenticated_context: HttpContext, built_chain: dict) -> None:
    created = await setup_pod(authenticated_context, built_chain["flavour_id"])
    variables = {"flavour": built_chain["flavour_id"], "repo": built_chain["repo_id"], "deployment": created["deployment"]["id"], "pod": created["pod"]["id"]}

    data = await execute(DESCRIBED, authenticated_context, variables)

    described = data["flavour"]
    assert described["descriptors"] == VANILLA
    # The variant is the flavour's name: `Flavour.flavour` is its image's digest.
    flavour = await models.Flavour.objects.aget(pk=built_chain["flavour_id"])
    assert flavour.flavour == "da60d36f7c1d48e69136699f4fcc901e" != described["descriptors"]["@kabinet/flavour_name"]
    assert {"id": str(flavour.pk), "descriptors": VANILLA} in data["flavours"]
    assert described["release"]["descriptors"] == {"@kabinet/version": "0.1.9", "@kabinet/channel": ""}
    assert described["definitions"] == [{"descriptors": CONVERT}]
    # The backend declared itself docker before anything was placed on it.
    assert data["deployment"]["descriptors"] == {"@kabinet/status": "PENDING", "@kabinet/backend_kind": "docker"}
    assert data["pod"]["descriptors"] == {"@kabinet/status": "PENDING", "@kabinet/backend_kind": "docker"}
    # A structure that declares no descriptors has none.
    assert described["release"]["app"]["descriptors"] == {}
    assert data["githubRepo"]["descriptors"] == {}

    declared = {s["identifier"]: {d["key"] for d in s["descriptors"]} for s in service.manifest()["structures"]}
    answered = {
        "@kabinet/flavour": described["descriptors"],
        "@kabinet/release": described["release"]["descriptors"],
        "@kabinet/app": described["release"]["app"]["descriptors"],
        "@kabinet/definition": described["definitions"][0]["descriptors"],
        "@kabinet/deployment": data["deployment"]["descriptors"],
        "@kabinet/pod": data["pod"]["descriptors"],
        "@kabinet/githubrepo": data["githubRepo"]["descriptors"],
    }
    assert {identifier: set(values) for identifier, values in answered.items()} == declared


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_the_field_answers_what_the_signal_carried(intake, authenticated_context: HttpContext) -> None:  # noqa: F811
    flavours = await sync_to_async(_catalogue)(authenticated_context.request.organization)
    cuda = str(flavours["cuda"].pk)

    # Waits out a third signal that should not come: a new flavour is announced once, already described.
    received = [r["json"] for r in await sync_to_async(intake.of)("@kabinet/flavour", count=3, timeout=2) if r["json"]["object"] == cuda]
    assert [signal["kind"] for signal in received] == ["CREATED"]
    data = await execute("query Flavour($id: ID!) { flavour(id: $id) { descriptors } }", authenticated_context, {"id": cuda})
    assert data["flavour"]["descriptors"] == received[0]["descriptors"] == CUDA


REQUIRED = """
    query Required($flavours: [RequiresInput!]!, $releases: [RequiresInput!]!, $definitions: [RequiresInput!]!) {
        flavours(filters: { requires: $flavours }) { id }
        releases(filters: { requires: $releases }) { id }
        definitions(filters: { requires: $definitions }) { id }
    }
"""

PLACED = """
    query Placed($requires: [RequiresInput!]!) {
        deployments(filters: { requires: $requires }) { id }
        pods(filters: { requires: $requires }) { id }
    }
"""


def _equals(key: str, value: object) -> list[dict]:
    return [{"key": key, "operator": "EQUALS", "value": value}]


async def _required(context: HttpContext, flavours: list | None = None, releases: list | None = None, definitions: list | None = None) -> dict[str, set[str]]:
    data = await execute(REQUIRED, context, {"flavours": flavours or [], "releases": releases or [], "definitions": definitions or []})
    return {field: {row["id"] for row in rows} for field, rows in data.items()}


async def _placed(context: HttpContext, requires: list) -> dict[str, set[str]]:
    data = await execute(PLACED, context, {"requires": requires})
    return {field: {row["id"] for row in rows} for field, rows in data.items()}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_port_requires_is_answered_from_the_stored_descriptors(authenticated_context: HttpContext) -> None:
    """A `requires` on a list filter returns exactly the rows whose stored descriptors satisfy it, and refuses a key nobody declares."""
    organization = authenticated_context.request.organization
    flavours = await sync_to_async(_catalogue)(organization)
    releases = await sync_to_async(_published)(organization)
    cuda, vanilla = str(flavours["cuda"].pk), str(flavours["vanilla"].pk)
    # ``release.json``'s one flavour requires a CUDA device (compute capability 7.0, no memory stated).
    starmist = {str(pk) for pk in await sync_to_async(list)(models.Flavour.objects.filter(release__in=releases.values()).values_list("pk", flat=True))}
    assert len(starmist) == 2

    async def flavours_with(requires: list) -> set[str]:
        return (await _required(authenticated_context, flavours=requires))["flavours"]

    assert await flavours_with(_equals("@kabinet/gpu", "none")) == {vanilla}
    assert await flavours_with(_equals("@kabinet/gpu", "cuda")) == {cuda, *starmist}
    assert await flavours_with([{"key": "@kabinet/arch", "operator": "CONTAINS", "value": "arm64"}]) == {cuda}
    assert await flavours_with([{"key": "@kabinet/min_vram_mb", "operator": "GTE", "value": 4000}]) == {cuda}
    assert await flavours_with([{"key": "@kabinet/min_ram_mb", "operator": "LTE", "value": 8000}]) == {vanilla, *starmist}
    # A preferred label is a kind of selector the flavour states, and no requirement.
    assert await flavours_with([{"key": "@kabinet/selector_kinds", "operator": "CONTAINS", "value": "label"}]) == {cuda}
    assert await flavours_with(_equals("@kabinet/flavour_name", "vanilla")) == {vanilla, *starmist}

    # A rescan writes the flavour again (``update_or_create``, a save): what it now states is stored.
    rebuilt = await sync_to_async(upsert_app_image)(_app_image("cuda", [{"kind": "rocm"}, {"kind": "cuda", "required": False}], "d" * 64), organization)
    assert str(rebuilt.pk) == cuda
    assert await flavours_with(_equals("@kabinet/gpu", "rocm")) == {cuda}
    assert await flavours_with([{"key": "@kabinet/arch", "operator": "CONTAINS", "value": "arm64"}]) == set()
    # Two vendors required at once: no one vendor's backend runs it.
    await sync_to_async(upsert_app_image)(_app_image("cuda", [{"kind": "rocm"}, {"kind": "cuda"}], "e" * 64), organization)
    assert await flavours_with(_equals("@kabinet/gpu", "multiple")) == {cuda}

    proper = {str(r.pk) for r in await sync_to_async(list)(models.Release.objects.filter(channel__isnull=True))}
    assert str(releases["proper"].pk) in proper and str(releases["main"].pk) not in proper
    assert (await _required(authenticated_context, releases=_equals("@kabinet/channel", "")))["releases"] == proper
    assert (await _required(authenticated_context, releases=_equals("@kabinet/channel", "main")))["releases"] == {str(releases["main"].pk)}

    convert = await models.Definition.objects.aget(organization=organization, name="Convert Omero")
    assert str(convert.pk) in (await _required(authenticated_context, definitions=_equals("@kabinet/n_args", 2)))["definitions"]
    assert str(convert.pk) not in (await _required(authenticated_context, definitions=_equals("@kabinet/n_args", 0)))["definitions"]

    # A key kabinet does not declare, or no longer does, is refused, not ignored.
    for key in ("@kabinet/builder", "@kabinet/scope", "@kabinet/flavour"):
        result = await execute_raw(REQUIRED, authenticated_context, {"flavours": _equals(key, "x"), "releases": [], "definitions": []})
        assert result.errors and "not a descriptor here" in result.errors[0].message, key


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_what_a_deployer_reports_is_stored(authenticated_context: HttpContext, flavour_id: str) -> None:
    """A status reported through the mutations, and a backend's new kind, are what a `requires` reads next."""
    created = await setup_pod(authenticated_context, flavour_id)
    deployment, pod = created["deployment"]["id"], created["pod"]["id"]

    await execute(UPDATE_POD, authenticated_context, {"input": {"pod": pod, "status": "RUNNING"}})
    await execute(
        "mutation ($input: UpdateDeploymentInput!) { updateDeployment(input: $input) { id } }",
        authenticated_context,
        {"input": {"deployment": deployment, "status": "RUNNING"}},
    )
    assert await _placed(authenticated_context, _equals("@kabinet/status", "RUNNING")) == {"deployments": {deployment}, "pods": {pod}}
    assert await _placed(authenticated_context, _equals("@kabinet/status", "PENDING")) == {"deployments": set(), "pods": set()}

    # The backend declares another kind: what runs on it says so, though none of it was saved.
    await execute(DECLARE_BACKEND, authenticated_context, {"input": {"name": "my-backend", "kind": "kubernetes"}})
    assert await _placed(authenticated_context, _equals("@kabinet/backend_kind", "kubernetes")) == {"deployments": {deployment}, "pods": {pod}}
    assert await _placed(authenticated_context, _equals("@kabinet/backend_kind", "docker")) == {"deployments": set(), "pods": set()}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_the_setup_job_repairs_what_is_owed(authenticated_context: HttpContext) -> None:
    """``restore_descriptors`` stores what a row that misses its descriptors owes."""
    flavours = await sync_to_async(_catalogue)(authenticated_context.request.organization)
    cuda = flavours["cuda"].pk

    # A row from before its descriptors were stored owes them; the setup job states them.
    await models.Flavour.objects.filter(pk=cuda).aupdate(stored_descriptors={})
    await sync_to_async(call_command)("restore_descriptors")
    assert (await models.Flavour.objects.aget(pk=cuda)).stored_descriptors == CUDA


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_sweep_for_one_organization_claims_only_its_rows(authenticated_context: HttpContext) -> None:
    """Every organization has the agent and its own schedule: a run must not do another's work.

    Covers every embedded model, because only two of the four keep their organization in a column
    of their own: a flavour's is its release's app's, a repo's is on its GitHub row.
    """
    organization = authenticated_context.request.organization
    elsewhere = await Organization.objects.acreate(identifier="static_issuer#elsewhere")

    def rows(organization: Organization) -> dict[type, int]:
        flavour = _catalogue(organization)["cuda"]
        definition = models.Definition.objects.get(flavours=flavour)
        return {models.App: flavour.release.app_id, models.Flavour: flavour.pk, models.Definition: definition.pk, models.Repo: flavour.repo_id}

    mine = await sync_to_async(rows)(organization)
    theirs = await sync_to_async(rows)(elsewhere)

    def stale(model: type, organization: str | None) -> set[int]:
        return set(stale_queryset(model, organization).values_list("pk", flat=True))

    def sweep() -> dict:
        for model in EMBEDDED:
            model.objects.filter(pk__in=[mine[model], theirs[model]]).update(embedding_model="another-model")
        for model in EMBEDDED:
            assert stale(model, "static_issuer#elsewhere") == {theirs[model]}, model.__name__
            assert stale(model, organization.identifier) == {mine[model]}, model.__name__
            assert stale(model, None) == {mine[model], theirs[model]}, model.__name__
        return agent.actions["reembed_stale"].function(organization=organization.identifier)

    assert await sync_to_async(sweep)() == {"reembedded": len(EMBEDDED)}

    def after() -> None:
        for model in EMBEDDED:
            assert model.objects.get(pk=mine[model]).embedding_model == engine.model_id(), model.__name__
            assert model.objects.get(pk=theirs[model]).embedding_model == "another-model", model.__name__

    await sync_to_async(after)()
