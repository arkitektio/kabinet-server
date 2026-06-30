from kante.types import Info
from bridge import types, inputs, models
from bridge.scoping import aget_for_org, get_for_org
import strawberry

from bridge.utils import aget_backend_for_info


async def create_pod(info: Info, input: inputs.CreatePodInput) -> types.Pod:
    """Register a running pod for a deployment on a backend."""
    parsed = input.to_pydantic()

    backend = await aget_backend_for_info(info)

    deployment = await aget_for_org(models.Deployment, info, id=parsed.deployment)

    if parsed.resource:
        resource = await aget_for_org(models.Resource, info, id=parsed.resource)
    else:
        resource = None

    pod, _ = await models.Pod.objects.aupdate_or_create(
        backend=backend,
        pod_id=parsed.local_id,
        defaults=dict(
            deployment=deployment,
            resource=resource,
            client_id=parsed.client_id,
        ),
    )

    return pod


async def update_pod(info: Info, input: inputs.UpdatePodInput) -> types.Pod:
    """Update the status of an existing pod."""
    parsed = input.to_pydantic()

    backend = await aget_backend_for_info(info)

    if not parsed.pod and not parsed.local_id:
        raise ValueError("Either pod or local_id must be set")

    if parsed.local_id:
        pod = await aget_for_org(
            models.Pod, info,
            backend=backend,
            pod_id=parsed.local_id,
        )

    if parsed.pod:
        pod = await aget_for_org(models.Pod, info, id=parsed.pod)

    pod.status = parsed.status
    await pod.asave()

    return pod


def dump_logs(info: Info, input: inputs.DumpLogsInput) -> types.LogDump:
    """Attach a captured log dump to a pod."""
    parsed = input.to_pydantic()

    pod = get_for_org(models.Pod, info, id=parsed.pod)

    log_dump = models.LogDump.objects.create(
        pod=pod,
        logs=parsed.logs,
    )

    return log_dump


async def delete_pod(info: Info, input: inputs.DeletePodInput) -> strawberry.ID:
    """Delete a pod and return its ID."""
    parsed = input.to_pydantic()

    pod = await aget_for_org(models.Pod, info, id=parsed.id)

    await pod.adelete()

    return parsed.id
