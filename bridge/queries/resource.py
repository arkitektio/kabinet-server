import strawberry
from kante.types import Info

from bridge import models, types
from bridge.scoping import get_for_org


def resource(info: Info, id: strawberry.ID) -> types.Resource:
    """Return a resource by id, scoped to the request's organization."""
    return get_for_org(models.Resource, info, id=id)
