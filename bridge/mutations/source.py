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


async def aimport_oci_repo(
    reference: str,
    organization: Organization,
    creator: User | None,
    channels: list[str] | None = None,
    reread: bool = False,
) -> models.OciRepo:
    """Import an OCI repository (or read an imported one again) and write the releases it carries.

    ``reread`` forgets which tags were read, so every tag is read again: a release tag is
    otherwise read once, so one refused and pushed again would never be taken.
    """
    registry, repository = oci.parse_reference(reference)

    repo = await models.OciRepo.objects.filter(registry=registry, repository=repository, organization=organization).afirst()
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

    if reread and repo.seen:
        repo.seen = {}
        await repo.asave(update_fields=["seen"])

    await oci.scan(repo)
    return repo


async def import_repo(info: Info, input: inputs.ImportRepoInput) -> types.OciRepo:
    """Import an OCI repository (or read an imported one again) and write the releases it carries."""
    parsed = input.to_pydantic()
    return await aimport_oci_repo(
        parsed.reference,
        info.context.request.organization,
        info.context.request.user,
        channels=parsed.channels,
        reread=parsed.reread,
    )
