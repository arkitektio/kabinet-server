from kante.types import Info
from bridge import types, models, scalars
from typing import AsyncGenerator
import strawberry
from bridge.backend import get_backend


async def flavour(
    info: Info,
    flavour_id: strawberry.ID,
) -> AsyncGenerator[types.FlavourUpdate, None]:
    """Join and subscribe to message sent to the given rooms."""

    backend = get_backend()
    flavour = await models.Flavour.objects.aget(id=flavour_id)

    async for message in backend.awatch_flavour(info,flavour):
        yield message



async def flavours(
    info: Info,
) -> AsyncGenerator[types.FlavourUpdate, None]:
    """Join and subscribe to message sent to the given rooms."""

    backend = get_backend()

    async for message in backend.awatch_flavours(info):
        yield message
