from bridge import types, models
import strawberry


def resource(id: strawberry.ID) -> types.Resource:
    """Return a dask cluster by id"""
    return models.Resource.objects.get(id=id)
