"""Collapse the duplicate rows that two never-enforced constraints allowed.

``GithubRepo`` and ``App`` declared their unique constraints under ``class Config``
instead of ``class Meta``. Django reads ``Meta``, so neither constraint ever reached the
database, and both tables have been accepting duplicates for as long as they have
existed. The next migration adds the constraints for real, which fails on any table that
already holds a duplicate -- so the duplicates have to go first.

**Rows are merged, never cascaded away.** ``Flavour.repo``, ``Release.app``,
``Deployment.flavour`` and ``Pod.deployment`` are all ``CASCADE``, so deleting one
duplicate ``App`` would take its releases, their flavours, their deployments and their
running pods with it. Each duplicate's children are moved onto the surviving row (the
lowest id, which is the oldest) and only the emptied husk is deleted.

Merging has to recurse, because the children carry unique constraints of their own:
``Release`` is unique on ``(app, version)`` and ``Flavour`` on ``(release, name)``. Two
duplicate Apps both holding a "0.1.9" release cannot simply both point at the survivor --
that collides -- so the release is merged into the surviving release instead, and the
same question is then asked of its flavours. ``Deployment`` has no unique constraint, so
the recursion bottoms out there.
"""

from django.db import migrations
from django.db.models import Count


def _merge_children(child_model, fk, doomed_pk, survivor_pk, unique_with, merge_child):
    """Move ``doomed``'s children onto ``survivor``, merging the ones that would collide.

    ``unique_with`` is the field that, together with the FK, must stay unique. A child
    whose key is free on the survivor is re-pointed; one whose key is taken is merged
    into the survivor's own child by ``merge_child`` and then deleted.
    """
    taken = {
        getattr(row, unique_with): row.pk
        for row in child_model.objects.filter(**{fk: survivor_pk})
    }

    for child in child_model.objects.filter(**{fk: doomed_pk}):
        key = getattr(child, unique_with)
        counterpart = taken.get(key)

        if counterpart is None:
            setattr(child, fk, survivor_pk)
            child.save(update_fields=[fk])
            taken[key] = child.pk
            continue

        merge_child(child.pk, counterpart)
        child.delete()


def dedupe_github_repos(apps, schema_editor):
    """One GithubRepo per (repo, user, branch, organization).

    Flavours simply follow the survivor: ``Flavour`` is unique on ``(release, name)``,
    which does not involve the repo, so re-pointing ``repo_id`` can never collide.
    """
    GithubRepo = apps.get_model("bridge", "GithubRepo")
    Flavour = apps.get_model("bridge", "Flavour")

    fields = ("repo", "user", "branch", "organization")
    duplicated = GithubRepo.objects.values(*fields).annotate(n=Count("id")).filter(n__gt=1)

    for group in duplicated:
        rows = list(GithubRepo.objects.filter(**{f: group[f] for f in fields}).order_by("id"))
        survivor, doomed = rows[0], rows[1:]

        for row in doomed:
            # `Flavour.repo` points at the `Repo` parent, whose pk the GithubRepo child shares.
            Flavour.objects.filter(repo_id=row.pk).update(repo_id=survivor.pk)
            row.delete()


def dedupe_apps(apps, schema_editor):
    """One App per (identifier, organization), merging releases and flavours as needed."""
    App = apps.get_model("bridge", "App")
    Release = apps.get_model("bridge", "Release")
    Flavour = apps.get_model("bridge", "Flavour")
    Deployment = apps.get_model("bridge", "Deployment")
    Definition = apps.get_model("bridge", "Definition")

    def merge_flavour(doomed_flavour_pk, survivor_flavour_pk):
        """Move a flavour's deployments and definition links onto its counterpart."""
        Deployment.objects.filter(flavour_id=doomed_flavour_pk).update(flavour_id=survivor_flavour_pk)

        # `Definition.flavours` is many-to-many; through-rows are re-pointed one at a
        # time so an existing (definition, survivor) pair is left alone rather than
        # violating the through table's own uniqueness.
        survivor_flavour = Flavour.objects.get(pk=survivor_flavour_pk)
        for definition in Definition.objects.filter(flavours__id=doomed_flavour_pk):
            definition.flavours.add(survivor_flavour)

    def merge_release(doomed_release_pk, survivor_release_pk):
        """Move a release's flavours onto its counterpart, merging colliding names."""
        _merge_children(Flavour, "release_id", doomed_release_pk, survivor_release_pk, "name", merge_flavour)

    fields = ("identifier", "organization")
    duplicated = App.objects.values(*fields).annotate(n=Count("id")).filter(n__gt=1)

    for group in duplicated:
        rows = list(App.objects.filter(**{f: group[f] for f in fields}).order_by("id"))
        survivor, doomed = rows[0], rows[1:]

        for row in doomed:
            _merge_children(Release, "app_id", row.pk, survivor.pk, "version", merge_release)
            row.delete()


def noop(apps, schema_editor):
    """Reverse is a no-op: merged rows cannot be un-merged."""


class Migration(migrations.Migration):

    dependencies = [
        ("bridge", "0002_collection_organization_definition_organization_and_more"),
    ]

    operations = [
        migrations.RunPython(dedupe_github_repos, noop),
        migrations.RunPython(dedupe_apps, noop),
    ]
