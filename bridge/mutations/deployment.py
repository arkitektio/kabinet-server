from koherent.types import Info
from bridge import types, inputs, models
from bridge.utils import aget_backend_for_info

async def create_deployment(
    info: Info, input: inputs.CreateDeploymentInput
) -> types.Deployment:
    """Create a new dask cluster on a bridge server"""

    backend = await aget_backend_for_info(info, input.instance_id)

    flavour = await models.Flavour.objects.aget(id=input.flavour)

    deployment = await models.Deployment.objects.acreate(
        flavour=flavour,
        backend=backend,
    )

    return deployment


async def update_deployment(
    info: Info, input: inputs.UpdateDeploymentInput
) -> types.Deployment:
    """Create a new dask cluster on a bridge server"""

    pod = await models.Pod.objects.aget(id=input.id)

    pod.status = input.status

    await pod.save()

    return pod
