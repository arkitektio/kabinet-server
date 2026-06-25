from kante.types import Info
from bridge import types, inputs, models
from bridge.utils import aget_backend_for_info


async def create_deployment(
    info: Info, input: inputs.CreateDeploymentInput
) -> types.Deployment:
    """Schedule a flavour onto a backend, creating a new deployment."""
    parsed = input.to_pydantic()

    backend = await aget_backend_for_info(info)

    flavour = await models.Flavour.objects.aget(id=parsed.flavour)

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
    """Update an existing deployment, addressed by its ID."""
    parsed = input.to_pydantic()

    deployment = await models.Deployment.objects.aget(id=parsed.deployment)

    # NOTE: the Deployment model has no status field today, so the status from the
    # input is not persisted; this resolver currently just returns the deployment.
    await deployment.asave()

    return deployment
