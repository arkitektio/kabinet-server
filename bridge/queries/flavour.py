from bridge import types, models, inputs
import strawberry


def flavour(id: strawberry.ID) -> types.Flavour:
    """Return a dask cluster by id"""
    return models.Flavour.objects.get(id=id)


def match_flavour(input: inputs.MatchFlavoursInput) -> types.Flavour:
    """Return the flavour that best matches the requested release and actions."""
    parsed = input.to_pydantic()

    flavours = models.Flavour.objects

    if parsed.release:
        flavours = flavours.filter(release_id=parsed.release)

    if parsed.actions:
        for action_hash in parsed.actions:
            flavours = flavours.filter(definitions__hash=action_hash)

    return flavours.first()
