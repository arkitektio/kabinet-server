from bridge import types, models
import strawberry
from rekuest_core.scalars import ActionHash


def definition(id: strawberry.ID | None = None, hash: ActionHash | None = None) -> types.Definition:
    """Return a dask cluster by id"""
    if id:
        return models.Definition.objects.get(id=id)
    if hash:
        return models.Definition.objects.get(hash=hash)

    raise Exception("Either hash or id needs to be provided")
