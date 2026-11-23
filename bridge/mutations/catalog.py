"""The organization's catalogs: adding, removing and reading one again, and importing what one
of its entries names.

Importing an entry is the import its kind always was: an OCI entry is ``importRepo`` of its
reference, a GitHub entry ``createGithubRepo`` of it. Being listed trusts nothing more.
"""

import strawberry
from kante.types import Info

from bridge import catalog as catalogs
from bridge import enums, inputs, models, types
from bridge.mutations.repo import _create_github_repo
from bridge.mutations.source import import_oci_repo
from bridge.scoping import aget_for_org


async def create_catalog(info: Info, input: inputs.CreateCatalogInput) -> types.Catalog:
    """Add the catalog at a URL to the organization (or read an added one again)."""
    parsed = input.to_pydantic()
    if not parsed.url.startswith(("https://", "http://")):
        raise ValueError(f"'{parsed.url}' is not an http(s) URL of a catalog")
    try:
        return await catalogs.add(
            parsed.url, info.context.request.organization, info.context.request.user
        )
    except catalogs.CatalogError as e:
        raise ValueError(str(e)) from e


async def delete_catalog(info: Info, input: inputs.DeleteCatalogInput) -> strawberry.ID:
    """Remove a catalog the organization added, with its entries. What was imported stays."""
    parsed = input.to_pydantic()
    catalog = await aget_for_org(models.Catalog, info, id=parsed.id)
    if catalog.ensured:
        raise ValueError(
            "The hub's config names this catalog (ensure_catalogs): only the hub's operator can remove it."
        )
    await catalog.adelete()
    return strawberry.ID(parsed.id)


async def refresh_catalog(
    info: Info, input: inputs.RefreshCatalogInput
) -> types.Catalog:
    """Read a catalog of the organization now, however recently it was read."""
    parsed = input.to_pydantic()
    catalog = await aget_for_org(models.Catalog, info, id=parsed.id)
    return await catalogs.refresh(catalog)


async def import_catalog_entry(
    info: Info, input: inputs.ImportCatalogEntryInput
) -> types.CatalogEntry:
    """Import the repository a catalog entry names into the organization."""
    parsed = input.to_pydantic()
    entry = await aget_for_org(models.CatalogEntry, info, id=parsed.id)
    organization = info.context.request.organization
    user = info.context.request.user

    if entry.kind == enums.CatalogEntryKind.OCI.value:
        channels = parsed.channels
        if channels is None:
            registry, _, repository = entry.reference.partition("/")
            imported = await models.OciRepo.objects.filter(
                registry=registry, repository=repository, organization=organization
            ).aexists()
            # The catalog's channels for a first import; an imported one keeps its own.
            channels = None if imported else entry.channels
        await import_oci_repo(entry.reference, channels, organization, user)
    else:
        await _create_github_repo(
            inputs.CreateGithubRepoInputModel(
                identifier=entry.reference, name=entry.reference
            ),
            organization,
            user,
        )
    return entry
