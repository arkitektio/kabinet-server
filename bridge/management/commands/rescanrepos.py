"""Read every repository again, and write what was published since.

    python manage.py rescanrepos                     # every organization
    python manage.py rescanrepos --organization SLUG # one

The same pass as the hook action ``rescan_sources``, for an operator (``konstruktor job run
kabinet rescanrepos``) or a schedule outside rekuest. Safe to run again: a tag already read is
not read twice, and a repository's scan state is overwritten by the next scan. It reads the
registries and GitHub, so it is a job and not part of the setup.
"""

from asgiref.sync import async_to_sync
from authentikate.models import Organization
from django.core.management.base import BaseCommand, CommandError

from bridge.repo.rescan import arescan_organization


class Command(BaseCommand):
    """Read every repository of every (or one) organization again."""

    help = "Read every tracked and imported repository again, and write the releases published since."

    def add_arguments(self, parser) -> None:  # noqa: ANN001 - argparse's parser
        parser.add_argument("--organization", help="The slug of the one organization to rescan. Every organization when omitted.")

    def handle(self, *args: object, organization: str | None = None, **kwargs: object) -> None:
        """Rescan each organization in turn and report what came of it."""
        organizations = Organization.objects.all()
        if organization is not None:
            organizations = organizations.filter(slug=organization)
            if not organizations.exists():
                raise CommandError(f"There is no organization '{organization}'.")

        for org in organizations:
            summary = async_to_sync(arescan_organization)(org)
            self.stdout.write(f"{org.slug}: {summary.repos} repositories, {summary.releases} new releases, {summary.unreadable} unreadable")
