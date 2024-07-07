from bridge import types, models
import strawberry


def backend(id: strawberry.ID) -> types.Backend:
    """Return a dask cluster by id"""
    return models.Backend.objects.get(id=id)
