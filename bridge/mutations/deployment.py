from graphql import GraphQLError
from kante.types import Info
from bridge import approvals, types, inputs, models
from bridge.scoping import aget_for_org
from bridge.utils import aget_backend_for_info


async def create_deployment(
    info: Info, input: inputs.CreateDeploymentInput
) -> types.Deployment:
    """Schedule a flavour onto a backend, creating a new deployment.

    Only under an active approval of the flavour's release that allows this backend:
    the deployed app will act as the approver, so the approver's consent — pinned to
    the release as it was when they gave it — is what makes the deployment legitimate.
    """
    parsed = input.to_pydantic()

    backend = await aget_backend_for_info(info)

    flavour = await aget_for_org(models.Flavour, info, id=parsed.flavour)
    approval = await aget_for_org(models.ReleaseApproval, info, id=parsed.approval)
    try:
        await approvals.acheck_deployable(approval, flavour, backend)
    except approvals.ApprovalError as e:
        raise GraphQLError(str(e)) from e

    # The approval is part of the deployment's identity: two users installing the same
    # flavour on one backend are two deployments, each acting as its own approver.
    deployment, _ = await models.Deployment.objects.aupdate_or_create(
        flavour=flavour,
        backend=backend,
        local_id=parsed.local_id,
        approval=approval,
        defaults={"secret_params": parsed.secret_params or {}},
    )

    return deployment


async def update_deployment(
    info: Info, input: inputs.UpdateDeploymentInput
) -> types.Deployment:
    """Update the status of an existing deployment, addressed by its ID.

    The status used to be accepted and silently dropped: the model had no field to put
    it in, so the resolver re-saved an unmodified row and returned it, and a client had
    no way to tell a successful update from a no-op. `Deployment.status` exists now and
    mirrors `Pod.status`.
    """
    parsed = input.to_pydantic()

    deployment = await aget_for_org(models.Deployment, info, id=parsed.deployment)

    deployment.status = parsed.status
    await deployment.asave()

    return deployment
