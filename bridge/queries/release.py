from bridge import types, models
from bridge.scoping import get_for_org
from kante.types import Info
import strawberry


def release(info: Info, id: strawberry.ID) -> types.Release:
    """Return a release by id, scoped to the request's organization."""
    return get_for_org(models.Release, info, id=id)
