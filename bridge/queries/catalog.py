"""The hub's catalogs. Listing them reads the ones not read for ``CATALOG_TTL`` seconds."""

import strawberry
from kante.types import Info

from bridge import catalog as catalogs
from bridge import models, types


async def catalogs_list(info: Info) -> list[types.Catalog]:
    """Every catalog the hub reads, each read again first when it is stale."""
    await catalogs.refresh_stale()
    return [catalog async for catalog in models.Catalog.objects.order_by("id")]


async def catalog(info: Info, id: strawberry.ID) -> types.Catalog:
    """One catalog, read again first when it is stale."""
    await catalogs.refresh_stale()
    return await models.Catalog.objects.aget(id=id)


def catalog_entry(info: Info, id: strawberry.ID) -> types.CatalogEntry:
    """One entry of a catalog. The hub's, so the same for every organization."""
    return models.CatalogEntry.objects.get(id=id)
