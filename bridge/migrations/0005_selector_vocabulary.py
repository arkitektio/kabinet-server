"""Rewrite stored ``Flavour.selectors`` JSON to the unified selector vocabulary.

The vocabulary change (see ``bridge/repo/selectors.py`` and ``docs/selectors.md``):

- ``cpu`` selectors no longer carry ``memory`` — system memory is the ``ram``
  selector's job. A stored ``cpu`` entry with ``memory`` loses the key and
  gains a sibling ``{"kind": "ram", "min": <memory>}``.
- Entries of a kind outside the vocabulary (there should be none — ``service``
  was never writable) are dropped rather than left to crash every read of the
  flavour, which is exactly what a stored ``cpu``/``oneapi`` entry used to do
  under the old split input/output models.

Irreversible in the strict sense (the reverse is a no-op): the forward rewrite
loses nothing but the position of the memory requirement.
"""

from django.db import migrations

KNOWN_KINDS = {"cpu", "ram", "cuda", "rocm", "oneapi", "label"}


def _rewrite(selectors: object) -> list:
    out = []
    for entry in selectors or []:
        if not isinstance(entry, dict) or entry.get("kind") not in KNOWN_KINDS:
            continue
        entry = dict(entry)
        ram = None
        if entry.get("kind") == "cpu":
            memory = entry.pop("memory", None)
            if memory is not None:
                ram = {"kind": "ram", "min": memory}
        out.append(entry)
        if ram is not None:
            out.append(ram)
    return out


def forwards(apps, schema_editor):
    Flavour = apps.get_model("bridge", "Flavour")
    for flavour in Flavour.objects.exclude(selectors=[]).iterator():
        rewritten = _rewrite(flavour.selectors)
        if rewritten != flavour.selectors:
            flavour.selectors = rewritten
            flavour.save(update_fields=["selectors"])


class Migration(migrations.Migration):
    dependencies = [
        ("bridge", "0004_deployment_status_alter_flavour_repo_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
