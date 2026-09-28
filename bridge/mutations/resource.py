from kante.types import Info
from bridge import types, inputs, models
from graphql import GraphQLError
from bridge.utils import aget_backend_for_info


async def declare_resource(info: Info, input: inputs.DeclareResourceInput) -> types.Resource:
    """Declare (register or update) a resource on one of your backends."""
    parsed = input.to_pydantic()

    # Only on your own backend: resources are what a deployer places pods on, so another
    # member must not be able to plant or rewrite them.
    own = await aget_backend_for_info(info)
    if str(own.id) != str(parsed.backend):
        raise GraphQLError("You can only declare resources on your own backend.")
    backend = own

    resource, _ = await models.Resource.objects.aupdate_or_create(
        backend=backend,
        resource_id=parsed.local_id,
        defaults={
            "qualifiers": [x.model_dump() for x in parsed.qualifiers] if parsed.qualifiers else None,
            "name": parsed.name or "unset",
        },
    )

    return resource
