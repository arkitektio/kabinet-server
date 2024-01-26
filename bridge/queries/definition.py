from bridge import types, models
import strawberry


def definition(id: strawberry.ID) -> types.Definition:
    """Return a dask cluster by id"""
    return models.Definition.objects.get(id=id)
