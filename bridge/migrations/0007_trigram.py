"""``pg_trgm``, for the ranking of ``search`` (``embeddings.search.hybrid_search``)."""

from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("bridge", "0006_created_through"),
    ]

    operations = [
        TrigramExtension(),
    ]
