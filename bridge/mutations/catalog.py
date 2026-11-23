"""Reading a catalog again, and importing what one of its entries names.

Importing an entry is the import its kind always was: an OCI entry is ``importRepo`` of its
reference, a GitHub entry ``createGithubRepo`` of it. Being listed trusts nothing more.
"""

from kante.types import Info

from bridge import catalog as catalogs
from bridge import enums, inputs, models, types
from bridge.mutations.repo import _create_github_repo
from bridge.mutations.source import import_oci_repo


async def refresh_catalog(
    info: Info, input: inputs.RefreshCatalogInput
) -> types.Catalog:
    """Read a catalog now, however recently it was read."""
    parsed = input.to_pydantic()
    catalog = await models.Catalog.objects.aget(id=parsed.id)
    return await catalogs.refresh(catalog)


async def import_catalog_entry(
    info: Info, input: inputs.ImportCatalogEntryInput
) -> types.CatalogEntry:
    """Import the repository a catalog entry names into the requesting organization."""
    parsed = input.to_pydantic()
    entry = await models.CatalogEntry.objects.aget(id=parsed.id)
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
