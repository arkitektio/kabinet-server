"""The organization's catalogs. Listing them adds the ones the hub's config names and reads
the ones not read for ``CATALOG_TTL`` seconds."""

import strawberry
from kante.types import Info

from bridge import catalog as catalogs
from bridge import models, types
from bridge.scoping import aget_for_org, get_for_org


async def catalogs_list(info: Info) -> list[types.Catalog]:
    """Every catalog of the organization, the config's included, each read first when stale."""
    organization = info.context.request.organization
    await catalogs.ensure(organization)
    await catalogs.refresh_stale(organization)
    return [
        catalog
        async for catalog in models.Catalog.objects.filter(
            organization=organization
        ).order_by("id")
    ]


async def catalog(info: Info, id: strawberry.ID) -> types.Catalog:
    """One catalog of the organization, read first when it is stale."""
    found = await aget_for_org(models.Catalog, info, id=id)
    await catalogs.refresh_stale(info.context.request.organization)
    return await models.Catalog.objects.aget(id=found.id)


def catalog_entry(info: Info, id: strawberry.ID) -> types.CatalogEntry:
    """One entry of a catalog of the organization."""
    return get_for_org(models.CatalogEntry, info, id=id)
