from koherent.types import Info
from bridge import types, inputs, models
from bridge.utils import aget_backend_for_info

async def declare_resource(
    info: Info, input: inputs.DeclareResourceInput
) -> types.Resource:
    """Create a new dask cluster on a bridge server"""

    backend = await aget_backend_for_info(info, input.instance_id)


    resource, _ = await models.Resource.objects.aupdate_or_create(
        backend=backend,
        resource_id=input.resource_id,
        defaults={
            "qualifiers": input.qualifiers,
            "name": input.name,
        },
    )


    return resource