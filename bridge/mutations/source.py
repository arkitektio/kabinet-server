"""Importing an OCI repository as a source of an app's releases.

There is one mutation, and it is the same act whether the repository is new or known:
read the registry, write what it carries. Importing a known repository reads it again.
"""

import logging

import aiohttp
from kante.types import Info

from bridge import inputs, models, types
from bridge.repo import oci

logger = logging.getLogger(__name__)


async def import_repo(info: Info, input: inputs.ImportRepoInput) -> types.OciRepo:
    """Import an OCI repository (or read an imported one again) and write the releases it carries."""
    parsed = input.to_pydantic()
    organization = info.context.request.organization
    registry, repository = oci.parse_reference(parsed.reference)

    repo = await models.OciRepo.objects.filter(registry=registry, repository=repository, organization=organization).afirst()
    if repo is None:
        # Read before it is stored: a repository that cannot be read is not imported.
        repo = models.OciRepo(
            registry=registry,
            repository=repository,
            organization=organization,
            name=f"{registry}/{repository}",
            creator=info.context.request.user,
            channels=parsed.channels or [],
        )
        async with aiohttp.ClientSession() as session:
            await oci.Registry(registry, repository, session).tags()
        await repo.asave()
    elif parsed.channels is not None and parsed.channels != repo.channels:
        repo.channels = parsed.channels
        await repo.asave(update_fields=["channels"])

    await oci.scan(repo)
    return repo
