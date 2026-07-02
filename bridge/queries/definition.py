from bridge import types, models
from bridge.scoping import get_for_org
from kante.types import Info
import strawberry
from rekuest_core.scalars import ActionHash


def definition(info: Info, id: strawberry.ID | None = None, hash: ActionHash | None = None) -> types.Definition:
    """Return an action definition by id or hash, scoped to the request's organization."""
    if id:
        return get_for_org(models.Definition, info, id=id)
    if hash:
        return get_for_org(models.Definition, info, hash=hash)

    raise Exception("Either hash or id needs to be provided")
