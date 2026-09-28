from kante.types import Info
from bridge import types, inputs, models
from bridge.scoping import aget_for_org
from bridge.utils import aget_backend_for_info
import strawberry
from authentikate.strawberry.directives import has_org_role
from graphql import GraphQLError


async def declare_backend(info: Info, input: inputs.DeclareBackendInput) -> types.Backend:
    """Declare (register or update) a backend for the current client."""
    parsed = input.to_pydantic()

    backend = await aget_backend_for_info(info)

    backend.name = parsed.name
    backend.kind = parsed.kind

    await backend.asave()

    return backend


async def delete_backend(info: Info, id: strawberry.ID) -> strawberry.ID:
    """Delete a backend: only the user who runs it, or an organization admin."""
    backend = await aget_for_org(models.Backend, info, id=id)
    if backend.user_id != info.context.request.user.id and not has_org_role(info, "admin"):
        raise GraphQLError("Only the backend's owner or an organization admin may delete it.")
    await backend.adelete()

    return id
