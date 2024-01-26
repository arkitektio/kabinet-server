from koherent.types import Info
from bridge import types, inputs, models
import logging
from typing import List

from bridge.utils import get_backend_for_info

async def create_pod(info: Info, input: inputs.CreatePodInput) -> types.Pod:
    """Create a new dask cluster on a bridge server"""

    backend = get_backend_for_info(info, input.instance_id)


    flavour = models.Deployment.objects.get(id=input.deployment)

    pod = await models.Pod.objects.acreate(
        backend=backend,
        flavour=flavour,
    )

    return pod


async def update_pod(info: Info, input: inputs.UpdatePodInput) -> types.Pod:
    """Create a new dask cluster on a bridge server"""

    pod = await models.Pod.objects.get(id=input.id)

    pod.status = input.status

    await pod.save()

    return pod


