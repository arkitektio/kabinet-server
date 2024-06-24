from bridge import types, models
import strawberry


def pod(id: strawberry.ID) -> types.Pod:
    """Return a dask cluster by id"""
    return models.Pod.objects.get(id=id)
