import strawberry
from kante.types import Info

from bridge import models, types
from bridge.scoping import get_for_org


def backend(info: Info, id: strawberry.ID) -> types.Backend:
    """Return a backend by id, scoped to the request's organization."""
    return get_for_org(models.Backend, info, id=id)
