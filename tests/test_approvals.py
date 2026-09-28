"""Release approvals gate deployments.

A deployed app acts as the user who approved its release (through a lok mandate),
so ``createDeployment`` must refuse anything that approval does not cover: a
revoked approval, a release re-published differently since, a backend the approver
did not allow.
"""

import pytest
from asgiref.sync import sync_to_async
from kante.context import HttpContext

from bridge import models
from tests.test_pods import APPROVAL_TARGET, CREATE_DEPLOYMENT, DECLARE_BACKEND, DECLARE_RESOURCE, approve
from tests.utils import execute, execute_raw

REVOKE = """
    mutation ($input: RevokeApprovalInput!) { revokeApproval(input: $input) { id revokedAt isActive } }
"""
RELEASE_APPROVALS = """
    query ($id: ID!) { release(id: $id) { approvals { id isStale isActive } } }
"""


async def _deploy(context, flavour_id, approval_id):
    return await execute_raw(
        CREATE_DEPLOYMENT, context, {"input": {"flavour": flavour_id, "localId": "dep-1", "approval": approval_id}}
    )


async def _declare_backend(context):
    return (await execute(DECLARE_BACKEND, context, {"input": {"name": "my-backend", "kind": "docker"}}))["declareBackend"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_deployment_requires_an_approval(authenticated_context: HttpContext, flavour_id: str) -> None:
    await _declare_backend(authenticated_context)
    result = await execute_raw(CREATE_DEPLOYMENT, authenticated_context, {"input": {"flavour": flavour_id, "localId": "dep-1"}})
    assert result.errors


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_approved_release_is_deployable_and_linked(authenticated_context: HttpContext, flavour_id: str) -> None:
    await _declare_backend(authenticated_context)
    approval = await approve(authenticated_context, flavour_id)
    assert approval["isActive"] and not approval["isStale"]
    assert approval["digest"].startswith("sha256:")

    result = await _deploy(authenticated_context, flavour_id, approval["id"])
    assert not result.errors, result.errors
    deployment = await models.Deployment.objects.aget(id=result.data["createDeployment"]["id"])
    assert str(deployment.approval_id) == approval["id"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_approving_refuses_a_digest_the_user_did_not_review(authenticated_context: HttpContext, flavour_id: str) -> None:
    release = (await execute(APPROVAL_TARGET, authenticated_context, {"id": flavour_id}))["flavour"]["release"]
    result = await execute_raw(
        """mutation ($input: ApproveReleaseInput!) { approveRelease(input: $input) { id } }""",
        authenticated_context,
        {"input": {"release": release["id"], "mandate": "m", "agent": "a", "digest": "sha256:not-it"}},
    )
    assert result.errors and "changed since you reviewed" in result.errors[0].message


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_republishing_the_release_makes_the_approval_stale(authenticated_context: HttpContext, flavour_id: str) -> None:
    await _declare_backend(authenticated_context)
    approval = await approve(authenticated_context, flavour_id)

    def _republish_with_more_scopes():
        release = models.Flavour.objects.get(id=flavour_id).release
        release.scopes = [*release.scopes, "write:everything"]
        release.save()
        return release.id

    release_id = await sync_to_async(_republish_with_more_scopes)()

    listed = (await execute(RELEASE_APPROVALS, authenticated_context, {"id": str(release_id)}))["release"]["approvals"]
    assert listed == [{"id": approval["id"], "isStale": True, "isActive": False}]

    result = await _deploy(authenticated_context, flavour_id, approval["id"])
    assert result.errors and "needs to be approved again" in result.errors[0].message


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_changed_image_makes_the_approval_stale(authenticated_context: HttpContext, flavour_id: str) -> None:
    await _declare_backend(authenticated_context)
    approval = await approve(authenticated_context, flavour_id)

    def _swap_image():
        flavour = models.Flavour.objects.select_related("image").get(id=flavour_id)
        flavour.image = models.DockerImage.objects.create(image_string="evil/image:latest", organization=flavour.image.organization)
        flavour.save()

    await sync_to_async(_swap_image)()
    result = await _deploy(authenticated_context, flavour_id, approval["id"])
    assert result.errors and "needs to be approved again" in result.errors[0].message


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_revoked_approval_is_refused(authenticated_context: HttpContext, flavour_id: str) -> None:
    await _declare_backend(authenticated_context)
    approval = await approve(authenticated_context, flavour_id)

    revoked = (await execute(REVOKE, authenticated_context, {"input": {"id": approval["id"]}}))["revokeApproval"]
    assert revoked["revokedAt"] and not revoked["isActive"]

    result = await _deploy(authenticated_context, flavour_id, approval["id"])
    assert result.errors and "revoked" in result.errors[0].message


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_approval_limited_to_other_backends_is_refused(authenticated_context: HttpContext, flavour_id: str) -> None:
    mine_id = (await _declare_backend(authenticated_context))["id"]

    def _someone_elses_backend():
        from authentikate.models import Client

        mine = models.Backend.objects.get(id=mine_id)
        other_client, _ = Client.objects.get_or_create(client_id="another-deployer")
        return models.Backend.objects.create(
            organization=mine.organization, user=mine.user, client=other_client, name="other", kind="docker"
        ).id

    other = await sync_to_async(_someone_elses_backend)()
    approval = await approve(authenticated_context, flavour_id, backends=[str(other)])
    assert approval["backends"] == [{"id": str(other)}]

    result = await _deploy(authenticated_context, flavour_id, approval["id"])
    assert result.errors and "not allowed" in result.errors[0].message


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_resources_can_only_be_declared_on_your_own_backend(authenticated_context: HttpContext, flavour_id: str) -> None:
    mine_id = (await _declare_backend(authenticated_context))["id"]

    def _foreign_backend():
        from authentikate.models import Client

        mine = models.Backend.objects.get(id=mine_id)
        other_client, _ = Client.objects.get_or_create(client_id="another-deployer")
        return models.Backend.objects.create(
            organization=mine.organization, user=mine.user, client=other_client, name="other", kind="docker"
        ).id

    other = await sync_to_async(_foreign_backend)()
    result = await execute_raw(
        DECLARE_RESOURCE, authenticated_context, {"input": {"backend": str(other), "localId": "res-1", "name": "gpu"}}
    )
    assert result.errors and "own backend" in result.errors[0].message


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_two_approvals_of_one_flavour_are_two_deployments(authenticated_context: HttpContext, flavour_id: str) -> None:
    """Installing the same flavour under two approvals must not merge them: each
    deployment keeps the approval (and thus the identity) it was made under."""
    await _declare_backend(authenticated_context)
    first = await approve(authenticated_context, flavour_id, mandate="mandate-a")
    second = await approve(authenticated_context, flavour_id, mandate="mandate-b")

    a = await _deploy(authenticated_context, flavour_id, first["id"])
    b = await _deploy(authenticated_context, flavour_id, second["id"])
    assert not a.errors and not b.errors, (a.errors, b.errors)
    assert a.data["createDeployment"]["id"] != b.data["createDeployment"]["id"]

    rows = [d async for d in models.Deployment.objects.filter(flavour_id=flavour_id).values_list("approval_id", flat=True)]
    assert sorted(str(r) for r in rows) == sorted([first["id"], second["id"]])
