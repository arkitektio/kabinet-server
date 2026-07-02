from bridge import types, models
from bridge.scoping import get_for_org
from kante.types import Info
import strawberry


def resource(info: Info, id: strawberry.ID) -> types.Resource:
    """Return a resource by id, scoped to the request's organization."""
    return get_for_org(models.Resource, info, id=id)
