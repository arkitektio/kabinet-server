"""Catalogs become an organization's (0005): the hub-wide rows of 0003 go first.

Nothing points at a catalog or an entry but each other, and every organization gets the
config's catalogs again the first time it lists them. A migration of its own: Postgres
refuses to alter a table with deferred constraint checks pending from rows deleted in the
same transaction.
"""

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def drop_hub_wide(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    apps.get_model("bridge", "CatalogEntry").objects.all().delete()
    apps.get_model("bridge", "Catalog").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("bridge", "0003_catalogs")]

    operations = [migrations.RunPython(drop_hub_wide, migrations.RunPython.noop)]
