from koherent.types import Info
from bridge import types, inputs, models
from bridge.utils import aget_backend_for_info

async def declare_backend(
    info: Info, input: inputs.DeclareBackendInput
) -> types.Backend:
    """Create a new dask cluster on a bridge server"""

    backend = await aget_backend_for_info(info, input.instance_id)

    backend.name = input.name
    backend.kind = input.kind

    await backend.asave()

    return backend