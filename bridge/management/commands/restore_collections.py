"""Put every definition in the collections its declaration names, where it is in none.

    python manage.py restore_collections

A definition is put in its collections when it is imported (``bridge/repo/db.py``,
``store_collections``). Definitions imported before that are in none; this reads their
declarations off the inspections their flavours store. Safe to run again: a definition already
in a collection is skipped, and one whose declaration names none stays in none.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from bridge import models
from bridge.management.commands.restore_bloks import definition_hash
from bridge.repo.db import store_collections

BATCH = 200


class Command(BaseCommand):
    help = "Put every definition in the collections its declaration names, where it is in none"

    def handle(self, *args: object, **options: object) -> None:
        restored = 0
        flavours = models.Flavour.objects.select_related(
            "release__app__organization"
        ).only("id", "inspection", "release__app__organization")
        for flavour in flavours.iterator(chunk_size=BATCH):
            organization = flavour.release.app.organization
            for implementation in (flavour.inspection or {}).get("implementations", []):
                names = (implementation.get("definition") or {}).get(
                    "collections"
                ) or []
                stored_as = definition_hash(implementation) if names else None
                if stored_as is None:
                    continue
                definition = (
                    models.Definition.objects.filter(
                        hash=stored_as,
                        organization=organization,
                        collections__isnull=True,
                    )
                    .only("id")
                    .first()
                )
                if definition is None:
                    continue
                with transaction.atomic():
                    store_collections(definition, names, organization)
                restored += 1
        self.stdout.write(f"Put {restored} definition(s) in their collections")
