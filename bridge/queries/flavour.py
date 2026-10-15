from bridge import types, models
from bridge.scoping import for_org, get_for_org
from kante.types import Info
import strawberry


def flavour(info: Info, id: strawberry.ID) -> types.Flavour:
    """Return a flavour by id, scoped to the request's organization."""
    return get_for_org(models.Flavour, info, id=id)


def flavour_blok(info: Info, id: strawberry.ID) -> types.FlavourBlok | None:
    """Return a blok of a flavour by its id (`<flavour id>:<key>`), scoped to the request's organization."""
    flavour_id, _, key = str(id).partition(":")
    flavour = for_org(models.Flavour, info).only(*types.BLOK_FIELDS).filter(id=flavour_id).first() if flavour_id.isdigit() else None
    if flavour is None:
        return None
    blok = next((blok for blok in flavour.bloks or [] if blok.get("key") == key), None)
    return types.flavour_blok(flavour, blok) if blok else None
