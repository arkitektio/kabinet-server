"""``descriptors`` on kabinet's types: what an object says about itself, from its structure's declaration.

One declaration (``kabinet_server.service``) feeds the manifest, the signals and this field, so the
tests hold the three to each other: the field answers what a signal about the object carries, in
the keys the manifest declares. And the agent's sweep, which every organization schedules for
itself, touches that organization's rows only.
"""

import pytest
from asgiref.sync import sync_to_async
from authentikate.models import Organization
from kante.context import HttpContext

from bridge import models
from embeddings import engine
from embeddings.healer import stale_queryset
from kabinet_server.hook_agent import agent
from kabinet_server.service import service
from tests.test_pods import setup_pod
from tests.test_signals import intake  # noqa: F401  the fixture
from tests.utils import execute

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


def _catalogue(organization: Organization) -> dict:
    """An app, a release, a flavour, a definition and a repo of ``organization``, keyed by the model that is embedded."""
    app = models.App.objects.create(identifier="live.arkitekt.segmentation", organization=organization)
    release = models.Release.objects.create(app=app, version="0.1.0")
    image = models.DockerImage.objects.create(image_string="jhnnsrs/seg:0.1.0", organization=organization)
    repo = models.GithubRepo.objects.create(name="arkitektio-apps/seg:main", user="arkitektio-apps", repo="seg", branch="main", organization=organization)
    flavour = models.Flavour.objects.create(release=release, name="cuda", flavour="cuda", image=image, repo=repo, builder="arkitekt", manifest={"identifier": app.identifier})
    definition = models.Definition.objects.create(hash="segment-hash", name="Segment", description="Segments cells", kind="FUNCTION", organization=organization)
    definition.flavours.add(flavour)
    return {models.App: app.pk, models.Flavour: flavour.pk, models.Definition: definition.pk, models.Repo: repo.pk}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_an_object_answers_the_descriptors_its_structure_declares(authenticated_context: HttpContext, built_chain: dict) -> None:
    created = await setup_pod(authenticated_context, built_chain["flavour_id"])
    variables = {"flavour": built_chain["flavour_id"], "repo": built_chain["repo_id"], "deployment": created["deployment"]["id"], "pod": created["pod"]["id"]}

    data = await execute(DESCRIBED, authenticated_context, variables)

    flavour = await models.Flavour.objects.select_related("release").aget(pk=built_chain["flavour_id"])
    definition = await models.Definition.objects.aget(flavours=flavour)
    deployment = await models.Deployment.objects.aget(pk=created["deployment"]["id"])
    pod = await models.Pod.objects.aget(pk=created["pod"]["id"])

    described = data["flavour"]
    assert described["descriptors"] == {"@kabinet/flavour": flavour.flavour, "@kabinet/builder": flavour.builder}
    assert {"id": str(flavour.pk), "descriptors": described["descriptors"]} in data["flavours"]
    assert described["release"]["descriptors"] == {"@kabinet/version": flavour.release.version}
    assert described["definitions"] == [{"descriptors": {"@kabinet/kind": "FUNCTION", "@kabinet/scope": definition.scope, "@kabinet/pure": definition.pure, "@kabinet/idempotent": definition.idempotent}}]
    assert data["deployment"]["descriptors"] == {"@kabinet/status": deployment.status}
    assert data["pod"]["descriptors"] == {"@kabinet/status": pod.status}
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
    rows = await sync_to_async(_catalogue)(authenticated_context.request.organization)

    received = [r for r in await sync_to_async(intake.of)("@kabinet/flavour") if r["json"]["object"] == str(rows[models.Flavour])]
    assert received, "the new flavour was not signalled"
    data = await execute("query Flavour($id: ID!) { flavour(id: $id) { descriptors } }", authenticated_context, {"id": str(rows[models.Flavour])})
    assert data["flavour"]["descriptors"] == received[0]["json"]["descriptors"] == {"@kabinet/flavour": "cuda", "@kabinet/builder": "arkitekt"}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_sweep_for_one_organization_claims_only_its_rows(authenticated_context: HttpContext) -> None:
    """Every organization has the agent and its own schedule: a run must not do another's work.

    Covers every embedded model, because only two of the four keep their organization in a column
    of their own: a flavour's is its release's app's, a repo's is on its GitHub row.
    """
    organization = authenticated_context.request.organization
    elsewhere = await Organization.objects.acreate(slug="elsewhere")
    mine = await sync_to_async(_catalogue)(organization)
    theirs = await sync_to_async(_catalogue)(elsewhere)

    def stale(model: type, organization: str | None) -> set[int]:
        return set(stale_queryset(model, organization).values_list("pk", flat=True))

    def sweep() -> dict:
        for model in EMBEDDED:
            model.objects.filter(pk__in=[mine[model], theirs[model]]).update(embedding_model="another-model")
        for model in EMBEDDED:
            assert stale(model, "elsewhere") == {theirs[model]}, model.__name__
            assert stale(model, organization.slug) == {mine[model]}, model.__name__
            assert stale(model, None) == {mine[model], theirs[model]}, model.__name__
        return agent.actions["reembed_stale"].function(organization=organization.slug)

    assert await sync_to_async(sweep)() == {"reembedded": len(EMBEDDED)}

    def after() -> None:
        for model in EMBEDDED:
            assert model.objects.get(pk=mine[model]).embedding_model == engine.model_id(), model.__name__
            assert model.objects.get(pk=theirs[model]).embedding_model == "another-model", model.__name__

    await sync_to_async(after)()
