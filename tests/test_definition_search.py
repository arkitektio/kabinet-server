"""Definitions embed their name + description on save; ``definitions(filters: { search })`` is hybrid.

Real model (potion-base-8M), real Postgres with pgvector -- what the service runs. Where a
test needs rows at *known* distances from the query it writes the vectors directly: ``e0`` is
the real embedding of the query, ``_vec(d)`` a unit vector at cosine distance ``d`` from it.
"""

import math
import uuid

import numpy as np
import pytest
from asgiref.sync import sync_to_async
from django.test import override_settings
from kante.context import HttpContext

from bridge.models import Definition
from embeddings import engine
from embeddings.healer import reembed_stale
from tests.utils import execute

QUERY = "detect cells"
SEARCH = "query($f: DefinitionFilter, $o: [DefinitionOrder!]){ definitions(filters: $f, ordering: $o){ name } }"


@sync_to_async
def _definition(ctx: HttpContext, name: str, description: str = "") -> Definition:
    return Definition.objects.create(name=name, description=description, hash=uuid.uuid4().hex, organization=ctx.request.organization)


def _unit_orthogonal(e0: np.ndarray) -> np.ndarray:
    axis = np.zeros_like(e0)
    axis[int(np.argmin(np.abs(e0)))] = 1.0
    u = axis - float(np.dot(axis, e0)) * e0
    return u / np.linalg.norm(u)


def _vec(e0: np.ndarray, distance: float) -> list[float]:
    theta = math.acos(1.0 - distance)
    return (math.cos(theta) * e0 + math.sin(theta) * _unit_orthogonal(e0)).astype(float).tolist()


async def _pin(row: Definition, e0: np.ndarray, distance: float | None, embedding_model: str | None = None) -> None:
    await Definition.objects.filter(pk=row.pk).aupdate(embedding=_vec(e0, distance) if distance is not None else None, embedding_model=embedding_model or engine.model_id())


async def _names(ctx: HttpContext, search: str, ordering: list | None = None) -> list[str]:
    data = await execute(SEARCH, ctx, {"f": {"search": search}, "o": ordering or []})
    return [d["name"] for d in data["definitions"]]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_embeds(authenticated_context: HttpContext) -> None:
    row = await _definition(authenticated_context, "Segment nuclei", "Find cell nuclei in a fluorescence image")
    await row.arefresh_from_db()
    assert row.embedding is not None and len(row.embedding) == 256
    assert abs(sum(x * x for x in row.embedding) - 1.0) < 1e-4
    assert row.embedding_model == engine.model_id()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_repo_scan_embeds_the_definition(authenticated_context: HttpContext, built_chain: dict) -> None:
    """The real write path (``parse_config`` -> ``update_or_create``) embeds too."""
    row = await Definition.objects.aget(name="Convert Omero")
    assert row.embedding is not None and row.embedding_model == engine.model_id()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_healer_reembeds_rows_of_another_model(authenticated_context: HttpContext) -> None:
    row = await _definition(authenticated_context, "Blur", "Gaussian blur of an image")
    await Definition.objects.filter(pk=row.pk).aupdate(embedding=None, embedding_model="some/older-model")
    assert await sync_to_async(reembed_stale)(Definition) == 1
    fresh = await Definition.objects.aget(pk=row.pk)
    assert fresh.embedding is not None and fresh.embedding_model == engine.model_id()
    assert await sync_to_async(reembed_stale)(Definition) == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_semantic_match_without_substring(authenticated_context: HttpContext) -> None:
    await _definition(authenticated_context, "Segment nuclei", "Find cell nuclei in a fluorescence image and detect every cell")
    await _definition(authenticated_context, "Export spreadsheet", "Write a table to an xlsx file on disk")
    names = await _names(authenticated_context, QUERY)
    assert "Segment nuclei" in names and "Export spreadsheet" not in names


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_lexical_only_when_disabled(authenticated_context: HttpContext) -> None:
    await _definition(authenticated_context, "Detect cells")
    await _definition(authenticated_context, "Segment nuclei", "detect cells in an image")
    with override_settings(EMBEDDINGS={**engine._settings(), "ENABLED": False}):
        assert await _names(authenticated_context, QUERY) == ["Detect cells"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_ranking_lexical_first_then_by_distance(authenticated_context: HttpContext) -> None:
    e0 = np.asarray(engine.embed_query(QUERY))
    await _pin(await _definition(authenticated_context, "Far"), e0, 0.5)
    await _pin(await _definition(authenticated_context, "Near"), e0, 0.1)
    await _pin(await _definition(authenticated_context, "Mid"), e0, 0.3)
    await _pin(await _definition(authenticated_context, "Beyond"), e0, 0.7)
    await _pin(await _definition(authenticated_context, "Detect cells here"), e0, None)
    assert await _names(authenticated_context, QUERY) == ["Detect cells here", "Near", "Mid", "Far"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_stale_embedding_model_is_not_a_vector_hit(authenticated_context: HttpContext) -> None:
    e0 = np.asarray(engine.embed_query(QUERY))
    await _pin(await _definition(authenticated_context, "Old model near"), e0, 0.05, "some/older-model")
    await _pin(await _definition(authenticated_context, "Old model detect cells"), e0, 0.05, "some/older-model")
    assert await _names(authenticated_context, QUERY) == ["Old model detect cells"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_explicit_ordering_replaces_the_ranking(authenticated_context: HttpContext) -> None:
    e0 = np.asarray(engine.embed_query(QUERY))
    await _pin(await _definition(authenticated_context, "First defined"), e0, 0.4)
    await _pin(await _definition(authenticated_context, "Second defined"), e0, 0.1)
    assert await _names(authenticated_context, QUERY) == ["Second defined", "First defined"]
    assert await _names(authenticated_context, QUERY, ordering=[{"definedAt": "ASC"}]) == ["First defined", "Second defined"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_unloadable_model_degrades_to_substring(authenticated_context: HttpContext) -> None:
    e0 = np.asarray(engine.embed_query(QUERY))
    await _pin(await _definition(authenticated_context, "Near"), e0, 0.05)
    await _definition(authenticated_context, "Detect cells")
    try:
        with override_settings(EMBEDDINGS={**engine._settings(), "MODEL_PATH": "/nonexistent/embeddings"}):
            engine.reset()
            assert await _names(authenticated_context, QUERY) == ["Detect cells"]
    finally:
        engine.reset()
