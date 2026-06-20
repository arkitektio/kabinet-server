from bridge import types, models
import strawberry
from rekuest_core.scalars import ActionHash


async def deployment(id: strawberry.ID) -> types.Deployment:
    """Return a dask cluster by id"""
    return await models.Deployment.objects.aget(id=id)
