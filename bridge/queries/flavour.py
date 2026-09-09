from bridge import types, models
from bridge.scoping import for_org, get_for_org
from kante.types import Info
import strawberry


def flavour(info: Info, id: strawberry.ID) -> types.Flavour:
    """Return a flavour by id, scoped to the request's organization."""
    return get_for_org(models.Flavour, info, id=id)
