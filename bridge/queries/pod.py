from bridge import types, models
import strawberry
from kante import Info
from bridge.utils import aget_backend_for_info


def pod(id: strawberry.ID) -> types.Pod:
    """Return a dask cluster by id"""
    return models.Pod.objects.get(id=id)


def pod_for_agent(client_id: strawberry.ID, instance_id: strawberry.ID) -> types.Pod | None:
    """Return a pod for a given agent"""

    try:
        return models.Pod.objects.get(client_id=client_id)
    except models.Pod.DoesNotExist:
        return None


async def my_pod_at(info: Info, instance_id: strawberry.ID, local_id: strawberry.ID) -> types.Pod:
    """Let a backend discover its own pod by local id"""
    backend = await aget_backend_for_info(info, instance_id)

    return await models.Pod.objects.aget(backend=backend, pod_id=local_id)
