from asgiref.sync import sync_to_async
from kante.types import Info
from bridge import types, inputs, models
from bridge.scoping import aget_for_org
from bridge.utils import aget_backend_for_info
import strawberry
from authentikate.strawberry.directives import has_org_role
from graphql import GraphQLError
from kabinet_server.service import service
from kabinet_server.contract import ADMIN


async def declare_backend(info: Info, input: inputs.DeclareBackendInput) -> types.Backend:
    """Declare (register or update) a backend for the current client."""
    parsed = input.to_pydantic()

    backend = await aget_backend_for_info(info)

    declared_kind = backend.kind != parsed.kind
    backend.name = parsed.name
    backend.kind = parsed.kind

    await backend.asave()

    if declared_kind:
        await sync_to_async(_restore_placed)(backend)

    return backend


def _restore_placed(backend: models.Backend) -> None:
    """Store the new ``@kabinet/backend_kind`` of what runs on the backend: a save of the backend saves none of them."""
    service.restore(models.Deployment.objects.filter(backend=backend))
    service.restore(models.Pod.objects.filter(backend=backend))


async def delete_backend(info: Info, id: strawberry.ID) -> strawberry.ID:
    """Delete a backend: only the user who runs it, or a Kabinet admin."""
    backend = await aget_for_org(models.Backend, info, id=id)
    if backend.user_id != info.context.request.user.id and not has_org_role(info, ADMIN):
        raise GraphQLError("Only the backend's owner or a Kabinet admin may delete it.")
    await backend.adelete()

    return id
