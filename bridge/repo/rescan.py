"""Reading every repository of an organization again: GitHub repos and OCI repos alike.

What the hook action ``rescan_sources`` and the ``rescanrepos`` job both run. One repository
that cannot be read does not stop the others; how each one went is recorded on it
(``bridge.repo.status``), so this only counts.
"""

import logging
from dataclasses import dataclass

from authentikate.models import Organization

from bridge import models
from bridge.mutations.repo import arescan_one

from . import oci

logger = logging.getLogger(__name__)


@dataclass
class RescanSummary:
    """What one pass over an organization's repositories came to."""

    repos: int = 0
    releases: int = 0
    unreadable: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"repos": self.repos, "releases": self.releases, "unreadable": self.unreadable}


async def arescan_organization(organization: Organization) -> RescanSummary:
    """Read every repository ``organization`` tracks or imported again, and write what was published since."""
    summary = RescanSummary()

    async for repo in models.OciRepo.objects.filter(organization=organization):
        summary.repos += 1
        try:
            summary.releases += len((await oci.scan(repo)).releases)
        except oci.RegistryError as e:
            logger.warning("Could not rescan %s: %s", repo, e)
            summary.unreadable += 1

    async for repo in models.GithubRepo.objects.filter(organization=organization):
        summary.repos += 1
        if not await arescan_one(repo, organization):
            summary.unreadable += 1

    return summary
