from koherent.types import Info
from bridge import types, inputs, models


async def create_deployment(
    info: Info, input: inputs.CreateDeploymentInput
) -> types.Deployment:
    """Create a new dask cluster on a bridge server"""

    flavour = models.Flavour.objects.get(id=input.d)

    pod = await models.Pod.objects.acreate(
        backend=input.backend,
        flavour=flavour,
    )

    return pod


async def update_deployment(
    info: Info, input: inputs.UpdateDeploymentInput
) -> types.Deployment:
    """Create a new dask cluster on a bridge server"""

    pod = await models.Pod.objects.get(id=input.id)

    pod.status = input.status

    await pod.save()

    return pod
