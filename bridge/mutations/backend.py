from kante.types import Info
from bridge import types, inputs, models
from bridge.scoping import aget_for_org
from bridge.utils import aget_backend_for_info
import strawberry


async def declare_backend(info: Info, input: inputs.DeclareBackendInput) -> types.Backend:
    """Declare (register or update) a backend for the current client."""
    parsed = input.to_pydantic()

    backend = await aget_backend_for_info(info)

    backend.name = parsed.name
    backend.kind = parsed.kind

    await backend.asave()

    return backend


async def delete_backend(info: Info, id: strawberry.ID) -> strawberry.ID:
    backend = await aget_for_org(models.Backend, info, id=id)
    await backend.adelete()

    return id
