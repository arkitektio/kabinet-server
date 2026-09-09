"""Persist the blok manifests an app image declares in its inspection.

``createAppImage`` accepted ``inspection.bloks`` (validated by ``BlokImplementationInputModel``)
and then dropped them; only implementations and requirements were stored.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add ``Flavour.bloks``."""

    dependencies = [
        ("bridge", "0005_selector_vocabulary"),
    ]

    operations = [
        migrations.AddField(
            model_name="flavour",
            name="bloks",
            field=models.JSONField(default=list, help_text="Blok implementation manifests declared by this flavour's inspection (rekuest_core BlokImplementationInput)."),
        ),
    ]
