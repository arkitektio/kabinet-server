from kante.types import Info
from bridge import types, inputs, models
from bridge.utils import aget_backend_for_info
import strawberry


async def declare_resource(info: Info, input: inputs.DeclareResourceInput) -> types.Resource:
    """Create a new dask cluster on a bridge server"""

    backend = await models.Backend.objects.aget(id=input.backend)

    resource, _ = await models.Resource.objects.aupdate_or_create(
        backend=backend,
        resource_id=input.local_id,
        defaults={
            "qualifiers": [strawberry.asdict(x) for x in input.qualifiers] if input.qualifiers else None,
            "name": input.name,
        },
    )

    return resource
