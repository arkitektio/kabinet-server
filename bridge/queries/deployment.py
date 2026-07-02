from bridge import types, models
from bridge.scoping import aget_for_org
from kante.types import Info
import strawberry


async def deployment(info: Info, id: strawberry.ID) -> types.Deployment:
    """Return a deployment by id, scoped to the request's organization."""
    return await aget_for_org(models.Deployment, info, id=id)
