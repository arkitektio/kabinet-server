from bridge import types, models
from bridge.scoping import aget_for_org, for_org, get_for_org
import strawberry
from kante.types import Info
from bridge.utils import aget_backend_for_info


def pod(info: Info, id: strawberry.ID) -> types.Pod:
    """Return a pod by id, scoped to the request's organization."""
    return get_for_org(models.Pod, info, id=id)


def pod_for_agent(info: Info, client_id: strawberry.ID) -> types.Pod | None:
    """Return a pod for a given agent, scoped to the request's organization."""

    try:
        return get_for_org(models.Pod, info, client_id=client_id)
    except models.Pod.DoesNotExist:
        return None


async def my_pod_at(info: Info, local_id: strawberry.ID) -> types.Pod:
    """Let a backend discover its own pod by local id"""
    backend = await aget_backend_for_info(info)

    return await aget_for_org(models.Pod, info, backend=backend, pod_id=local_id)
