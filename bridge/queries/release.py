from bridge import types, models
import strawberry


def release(id: strawberry.ID) -> types.Release:
    """Return a dask cluster by id"""
    return models.Release.objects.get(id=id)



