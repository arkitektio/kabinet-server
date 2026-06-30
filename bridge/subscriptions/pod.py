from kante.types import Info
from bridge import types, models, messages
from bridge.scoping import aget_for_org
from typing import AsyncGenerator
from bridge import channels
import strawberry


@strawberry.type
class PodEvent:
    create: types.Pod | None = None
    update: types.Pod | None = None
    delete: strawberry.ID | None = None


async def pod(
    info: Info,
    pod_id: strawberry.ID,
) -> AsyncGenerator[PodEvent, None]:
    """Join and subscribe to message sent to the given rooms."""

    # Scope the subscribe to the request's organization: aget_for_org raises
    # DoesNotExist for a pod in another org, blocking cross-tenant subscriptions.
    pod = await aget_for_org(models.Pod, info, id=pod_id)

    async for message in channels.pod_channel.alisten(info, [pod_id]):
        if message.create:
            return PodEvent(create=await aget_for_org(models.Pod, info, id=message.create))
        if message.update:
            return PodEvent(update=await aget_for_org(models.Pod, info, id=message.update))
        if message.delete:
            return PodEvent(delete=message.delete)
            
        


async def pods(
    info: Info,
) -> AsyncGenerator[PodEvent, None]:
    """Join and subscribe to message sent to the given rooms."""

    async for message in channels.pod_channel.alisten(info, ["all"]):
        if message.create:
            return PodEvent(create=await aget_for_org(models.Pod, info, id=message.create))
        if message.update:
            return PodEvent(update=await aget_for_org(models.Pod, info, id=message.update))
        if message.delete:
            return PodEvent(delete=message.delete)
            