from bridge import types, models, inputs
from bridge.scoping import for_org, get_for_org
from kante.types import Info
import strawberry


def flavour(info: Info, id: strawberry.ID) -> types.Flavour:
    """Return a flavour by id, scoped to the request's organization."""
    return get_for_org(models.Flavour, info, id=id)


def match_flavour(info: Info, input: inputs.MatchFlavoursInput) -> types.Flavour:
    """Return the flavour that best matches the requested release and actions."""
    parsed = input.to_pydantic()

    flavours = for_org(models.Flavour, info)

    if parsed.release:
        flavours = flavours.filter(release_id=parsed.release)

    if parsed.actions:
        for action_hash in parsed.actions:
            flavours = flavours.filter(definitions__hash=action_hash)

    return flavours.first()
