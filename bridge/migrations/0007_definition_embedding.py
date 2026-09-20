"""Definitions embed their name + description (pgvector) for the semantic ``search`` filter.

``VectorExtension`` creates ``vector`` in this database. It is not a ``trusted`` extension, so
this needs the superuser -- which is what the services connect as. On a cluster whose init
script already created it (daten images that carry pgvector) it is a no-op. A daten image
without pgvector fails here, loudly, which is the right place to fail.

The backfill embeds every existing definition in this transaction. That is cheap (a static
model, ~1 ms a row) and means search works the moment the release is up; the in-process
healer (``embeddings.healer``, started from ``kabinet_server/asgi.py``) would otherwise do it
within a sweep.
"""

from typing import Any

import pgvector.django.vector
from django.conf import settings
from django.db import migrations, models
from pgvector.django import VectorExtension

BATCH = 500


def backfill_definition_embeddings(apps: Any, schema_editor: Any) -> None:
    """Embed every definition that has text, with the configured model; no-op when disabled."""
    from embeddings import engine

    if not engine.enabled():
        return
    Definition = apps.get_model("bridge", "Definition")
    current = engine.model_id()
    queryset = Definition.objects.exclude(embedding_model=current).order_by("pk").only("pk", "name", "description")
    while True:
        rows = list(queryset[:BATCH])
        if not rows:
            return
        sources = [engine.source_text(row.name, row.description) for row in rows]
        vectors = iter(engine.embed_texts([source for source in sources if source is not None]))
        for row, source in zip(rows, sources, strict=True):
            row.embedding = next(vectors) if source is not None else None
            row.embedding_model = current
        Definition.objects.bulk_update(rows, ["embedding", "embedding_model"])


class Migration(migrations.Migration):
    """Extension, the two columns, the healer's index, and the backfill -- one transaction."""

    dependencies = [
        ("authentikate", "0006_alter_app_identifier_alter_release_unique_together"),
        ("bridge", "0006_flavour_bloks"),
    ]

    operations = [
        VectorExtension(),
        migrations.AddField(
            model_name="definition",
            name="embedding",
            field=pgvector.django.vector.VectorField(blank=True, dimensions=256, editable=False, help_text="Unit-length embedding of name + description, by the model named in embedding_model; NULL when there is no text to embed", null=True),
        ),
        migrations.AddField(
            model_name="definition",
            name="embedding_model",
            field=models.CharField(blank=True, default="", editable=False, help_text="The embedding model that produced `embedding`. Rows whose value differs from the configured model are re-embedded in-process and are excluded from vector search until then", max_length=200),
        ),
        migrations.AddIndex(
            model_name="definition",
            index=models.Index(fields=["embedding_model"], name="definition_emb_model_idx"),
        ),
        migrations.RunPython(backfill_definition_embeddings, migrations.RunPython.noop),
    ]
