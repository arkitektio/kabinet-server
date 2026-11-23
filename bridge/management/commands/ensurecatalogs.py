"""Make the hub's catalogs exactly the ones the config names.

    python manage.py ensurecatalogs

Reads ``settings.ENSURE_CATALOGS`` (``ensure_catalogs`` in the config; see CONFIG.md): a
catalog it names that has no row gets one, and a row it no longer names is deleted with its
entries (what organizations imported from it stays theirs). Touches the database only: the
files are read when the catalogs are listed, not here, so a hub without internet sets up the
same. Running it again changes nothing.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from bridge import models


class Command(BaseCommand):
    """Create the catalogs the config names and delete the ones it no longer does."""

    help = "Make the hub's catalogs exactly the ones ENSURE_CATALOGS names."

    def handle(self, *args: object, **kwargs: object) -> None:
        """Sync the catalog rows to the config."""
        urls: list[str] = list(dict.fromkeys(settings.ENSURE_CATALOGS))
        with transaction.atomic():
            created = [
                url for url in urls if models.Catalog.objects.get_or_create(url=url)[1]
            ]
            removed = list(
                models.Catalog.objects.exclude(url__in=urls).values_list(
                    "url", flat=True
                )
            )
            models.Catalog.objects.filter(url__in=removed).delete()
        for url in created:
            self.stdout.write(f"Added catalog {url}")
        for url in removed:
            self.stdout.write(f"Removed catalog {url}")
