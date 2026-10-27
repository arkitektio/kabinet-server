"""Store what the bloks of every flavour draw, where a flavour has none stored.

    python manage.py restore_bloks [--all]

A flavour stores its bloks' renders and its actions' logos when it is imported
(``bridge/repo/bloks.py``). Flavours imported before that have neither; this reads them off the
stored inspection. ``--all`` renders every flavour again, after the parser changed, and every
blok a repository publishes (``RepoBlok``, always rendered when it is scanned). Safe to run
again: a flavour with renders is skipped, and ``--all`` writes the same renders twice.
"""

from django.core.management.base import BaseCommand

from bridge import models
from bridge.repo import bloks
from rekuest_core.inputs.models import DefinitionInputModel

BATCH = 200


def definition_hash(implementation: dict) -> str | None:
    """The hash an implementation's definition is stored under; None when it no longer validates."""
    try:
        return DefinitionInputModel.model_validate(implementation["definition"]).unique_hash
    except Exception:  # noqa: BLE001 - an old inspection the models refuse has no logo to name
        return None


def restore(flavour: models.Flavour) -> None:
    """Fill ``flavour``'s renders and action logos from what it stores (not saved)."""
    inspection = flavour.inspection or {}
    flavour.blok_renders = bloks.render_bloks(flavour.bloks or [])
    flavour.action_logos = bloks.action_logos(
        (definition_hash(implementation), implementation.get("logo"))
        for implementation in inspection.get("implementations", [])
        if implementation.get("logo")
    )
    flavour.action_logos.pop(None, None)


class Command(BaseCommand):
    help = "Store what the bloks of every flavour draw where it has none stored (--all: of every flavour)"

    def add_arguments(self, parser) -> None:  # noqa: ANN001
        parser.add_argument("--all", action="store_true", help="Render every flavour's bloks again")

    def handle(self, *args, **options) -> None:  # noqa: ANN002, ANN003
        flavours = models.Flavour.objects.only("id", "bloks", "inspection", "blok_renders", "action_logos")
        if not options["all"]:
            flavours = flavours.filter(blok_renders={}).exclude(bloks=[])

        changed: list[models.Flavour] = []
        for flavour in flavours.iterator(chunk_size=BATCH):
            restore(flavour)
            changed.append(flavour)
        # Neither field is read by a describer, so the rows' descriptors stay as they are.
        models.Flavour.objects.bulk_update(changed, ["blok_renders", "action_logos"], batch_size=BATCH)
        self.stdout.write(f"Rendered the bloks of {len(changed)} flavour(s)")

        if options["all"]:
            repo_bloks: list[models.RepoBlok] = []
            declared = bloks.DECLARED
            for blok in models.RepoBlok.objects.only("id", "source", "context", *declared).iterator(chunk_size=BATCH):
                render = bloks.render_blok({"source": blok.source, "context": blok.context, **{key: getattr(blok, key) for key in declared}})
                blok.component_tree, blok.hash, blok.parse_error = render["component_tree"], render["hash"], render["parse_error"]
                repo_bloks.append(blok)
            models.RepoBlok.objects.bulk_update(repo_bloks, ["component_tree", "hash", "parse_error"], batch_size=BATCH)
            self.stdout.write(f"Rendered {len(repo_bloks)} repository blok(s)")
