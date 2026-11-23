"""Importing an OCI repository as a source of an app's releases.

There is one mutation, and it is the same act whether the repository is new or known:
read the registry, write what it carries. Importing a known repository reads it again.
"""

import logging

import aiohttp
from authentikate.models import Organization, User
from kante.types import Info

from bridge import inputs, models, types
from bridge.repo import oci

logger = logging.getLogger(__name__)


async def import_oci_repo(
    reference: str,
    channels: list[str] | None,
    organization: Organization,
    creator: User | None,
) -> models.OciRepo:
    """Import an OCI repository into ``organization`` (or read an imported one again).

    ``channels`` replaces what is followed; ``None`` keeps it.
    """
    registry, repository = oci.parse_reference(reference)

    repo = await models.OciRepo.objects.filter(
        registry=registry, repository=repository, organization=organization
    ).afirst()
    if repo is None:
        # Read before it is stored: a repository that cannot be read is not imported.
        repo = models.OciRepo(
            registry=registry,
            repository=repository,
            organization=organization,
            name=f"{registry}/{repository}",
            creator=creator,
            channels=channels or [],
        )
        async with aiohttp.ClientSession() as session:
            await oci.Registry(registry, repository, session).tags()
        await repo.asave()
    elif channels is not None and channels != repo.channels:
        repo.channels = channels
        await repo.asave(update_fields=["channels"])

    await oci.scan(repo)
    return repo


async def import_repo(info: Info, input: inputs.ImportRepoInput) -> types.OciRepo:
    """Import an OCI repository (or read an imported one again) and write the releases it carries."""
    parsed = input.to_pydantic()
    return await import_oci_repo(
        parsed.reference,
        parsed.channels,
        info.context.request.organization,
        info.context.request.user,
    )
