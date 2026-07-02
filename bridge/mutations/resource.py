from kante.types import Info
from bridge import types, inputs, models
from bridge.scoping import aget_for_org
from bridge.utils import aget_backend_for_info


async def declare_resource(info: Info, input: inputs.DeclareResourceInput) -> types.Resource:
    """Declare (register or update) a resource on one of your backends."""
    parsed = input.to_pydantic()

    backend = await aget_for_org(models.Backend, info, id=parsed.backend)

    resource, _ = await models.Resource.objects.aupdate_or_create(
        backend=backend,
        resource_id=parsed.local_id,
        defaults={
            "qualifiers": [x.model_dump() for x in parsed.qualifiers] if parsed.qualifiers else None,
            "name": parsed.name or "unset",
        },
    )

    return resource
