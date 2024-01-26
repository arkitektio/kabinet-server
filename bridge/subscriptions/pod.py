from kante.types import Info
from bridge import types, models, gateways, messages
from typing import AsyncGenerator
import strawberry


async def pod(
    info: Info,
    pod_id: strawberry.ID,
) -> AsyncGenerator[messages.PodUpdateMessage, None]:
    """Join and subscribe to message sent to the given rooms."""

    pod = await models.Pod.objects.aget(id=pod_id)

    async for message in gateways.pod_gateway.alisten(info, [pod_id]):
        yield message


async def pods(
    info: Info,
) -> AsyncGenerator[messages.PodUpdateMessage, None]:
    """Join and subscribe to message sent to the given rooms."""

    async for message in gateways.pod_gateway.alisten(info, ["all"]):
        yield message
