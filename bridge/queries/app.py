from bridge import types, models
from bridge.scoping import get_for_org
from kante.types import Info
import strawberry


def app(info: Info, id: strawberry.ID) -> types.App:
    """Return an app by id, scoped to the request's organization."""
    return get_for_org(models.App, info, id=id)
