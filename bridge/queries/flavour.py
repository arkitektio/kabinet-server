from bridge import types, models, inputs
import strawberry


def flavour(id: strawberry.ID) -> types.Flavour:
    """Return a dask cluster by id"""
    return models.Flavour.objects.get(id=id)


def match_flavour(input: inputs.MatchFlavoursInput) -> types.Flavour:
    """Return a dask cluster by id"""

    flavours = models.Flavour.objects

    if input.release:
        flavours = flavours.filter(release_id=input.release)

    if input.actions:
        for action_hash in input.actions:
            flavours = flavours.filter(definitions__hash=action_hash)

    return flavours.first()
