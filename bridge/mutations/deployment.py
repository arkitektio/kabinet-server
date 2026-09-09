from kante.types import Info
from bridge import types, inputs, models
from bridge.scoping import aget_for_org
from bridge.utils import aget_backend_for_info


async def create_deployment(
    info: Info, input: inputs.CreateDeploymentInput
) -> types.Deployment:
    """Schedule a flavour onto a backend, creating a new deployment."""
    parsed = input.to_pydantic()

    backend = await aget_backend_for_info(info)

    flavour = await aget_for_org(models.Flavour, info, id=parsed.flavour)

    deployment, _ = await models.Deployment.objects.aupdate_or_create(
        flavour=flavour,
        backend=backend,
        local_id=parsed.local_id,
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
