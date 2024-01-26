from koherent.types import Info
from bridge import types, inputs, models
import logging
from typing import List


async def create_pod(info: Info, input: inputs.CreatePodInput) -> types.Pod:
    """Create a new dask cluster on a bridge server"""

    flavour = models.Flavour.objects.get(id=input.d)

    pod = await models.Pod.objects.acreate(
        backend=input.backend,
        flavour=flavour,
    )

    return pod


async def update_pod(info: Info, input: inputs.UpdatePodInput) -> types.Pod:
    """Create a new dask cluster on a bridge server"""

    pod = await models.Pod.objects.get(id=input.id)

    pod.status = input.status

    await pod.save()

    return pod
