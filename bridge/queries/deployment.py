from bridge import types, models
import strawberry
from rekuest_core.scalars import ActionHash


async def deployment(id: strawberry.ID) -> types.Deployment:
    print("HALALALLALALA")
    """Return a dask cluster by id"""
    z = await models.Deployment.objects.aget(id=id)

    print(z, "GOT THE SHIT")
    return z
