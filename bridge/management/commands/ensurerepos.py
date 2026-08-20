"""Ensure the repositories named in ``REPO_MAP`` exist for their organizations.

    python manage.py ensurerepos

Reads ``settings.REPO_MAP`` (``repo_map`` in the config; see CONFIG.md), creates each
organization if needed, and tracks every repository listed under it. Idempotent: a repo
that already exists is scanned again rather than duplicated.
"""

from asgiref.sync import async_to_sync
from authentikate.models import Organization
from django.conf import settings
from django.core.management.base import BaseCommand
from pydantic import BaseModel

from bridge import inputs
from bridge.mutations.repo import _create_github_repo


class RepoMap(BaseModel):
    """One organization and the repository identifiers it should track."""

    organization: str
    repos: list[str]


class RepoMapSettings(BaseModel):
    """The validated shape of ``settings.REPO_MAP``."""

    repo_map: list[RepoMap]


async def create_github_repos(repo_map: list[RepoMap]) -> None:
    """Track every repository in ``repo_map``, reporting failures without aborting."""
    for entry in repo_map:
        organization, _ = await Organization.objects.aget_or_create(slug=entry.organization)

        for repo_identifier in entry.repos:
            # `_create_github_repo` takes the *pydantic* input model, not the strawberry
            # one. This used to pass `inputs.CreateGithubRepoInput`, so the command could
            # not have worked -- and the failure was hidden behind an `except: raise e`
            # followed by an unreachable `print`.
            repo_input = inputs.CreateGithubRepoInputModel(
                identifier=repo_identifier,
                name=repo_identifier,
            )

            try:
                await _create_github_repo(repo_input, organization, None)
            except Exception as e:
                # One unreachable repo should not stop the rest from being provisioned;
                # this runs at deploy time, where a partial result beats no result.
                print(f"Error creating repo {repo_identifier} for {entry.organization}: {e}")


class Command(BaseCommand):
    """Provision the configured repositories for each configured organization."""

    help = "Ensure the repositories named in REPO_MAP exist for their organizations."

    def handle(self, *args: object, **kwargs: object) -> None:
        """Validate REPO_MAP and provision every repository it names."""
        validated = RepoMapSettings(repo_map=settings.REPO_MAP)

        async_to_sync(create_github_repos)(validated.repo_map)
