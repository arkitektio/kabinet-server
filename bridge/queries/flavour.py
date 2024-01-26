from bridge import types, models, inputs
import strawberry


def flavour(id: strawberry.ID) -> types.Flavour:
    """Return a dask cluster by id"""
    return models.Flavour.objects.get(id=id)



def best_flavour(release: strawberry.ID, environment: inputs.EnvironmentInput ) -> types.Flavour:
    """Return a dask cluster by id"""

    t = models.Flavour.objects.filter(release=release).first()
    return t