from koherent.types import Info
from bridge import types, inputs, models
import logging
from typing import List
import strawberry

from bridge.utils import aget_backend_for_info

async def create_pod(info: Info, input: inputs.CreatePodInput) -> types.Pod:
    """Create a new dask cluster on a bridge server"""

    backend = await aget_backend_for_info(info, input.instance_id)


    deployment = await models.Deployment.objects.aget(id=input.deployment)

    if input.resource:
        resource = await models.Resource.objects.aget(id=input.resource)
    else:
        resource = None

    pod, _ = await models.Pod.objects.aupdate_or_create(
        backend=backend,
        pod_id=input.local_id,
        defaults=dict(
            deployment=deployment,
            resource=resource,
            client_id=input.client_id,
        )
    )

    return pod


async def update_pod(info: Info, input: inputs.UpdatePodInput) -> types.Pod:
    """Create a new dask cluster on a bridge server"""

    backend = await aget_backend_for_info(info, input.instance_id)

    if not input.pod and not input.local_id:
        raise ValueError("Either pod or local_id must be set")

    if input.local_id:
        pod = await models.Pod.objects.aget(
            backend=backend,
            pod_id=input.local_id,
        )
    
    if input.pod:
        pod = await models.Pod.objects.aget(
            id=input.pod
        )


    pod.status = input.status
    await pod.asave()

    return pod


def dump_logs(info: Info, input: inputs.DumpLogsInput) -> types.LogDump:
    """Create a new dask cluster on a bridge server"""

    pod = models.Pod.objects.get(id=input.pod)

    log_dump = models.LogDump.objects.create(
        pod=pod,
        logs=input.logs,
    )

    return log_dump



async def delete_pod(info: Info, input: inputs.DeletePodInput) -> strawberry.ID:
    """Create a new dask cluster on a bridge server"""


    pod = await models.Pod.objects.aget(id=input.id
    )

    await pod.adelete()

    return pod