import strawberry
from kante.types import Info

from bridge import models, types
from bridge.scoping import aget_for_org


async def deployment(info: Info, id: strawberry.ID) -> types.Deployment:
    """Return a deployment by id, scoped to the request's organization."""
    return await aget_for_org(models.Deployment, info, id=id)
