from bridge import types, models
from bridge.scoping import get_for_org
from kante.types import Info
import strawberry


def backend(info: Info, id: strawberry.ID) -> types.Backend:
    """Return a backend by id, scoped to the request's organization."""
    return get_for_org(models.Backend, info, id=id)
