"""Grouping definitions: `Definition.similarDefinitions`, `filters: { similarTo }`, and the new facets.

Real model, real pgvector -- the same setup as ``tests/test_definition_search.py``, whose
helpers for writing vectors at a *known* distance are reused here: a neighbourhood test
that cannot say how far apart its rows are is not testing an ordering.
"""

import uuid

import numpy as np
import pytest
from asgiref.sync import sync_to_async
from kante.context import HttpContext

from bridge.models import Collection, Definition, Protocol
from embeddings import engine
from tests.test_definition_search import _vec
from tests.utils import execute

SIMILAR = """
query($id: ID!, $limit: Int, $maxDistance: Float, $f: DefinitionFilter) {
    definition(id: $id) { name similarDefinitions(limit: $limit, maxDistance: $maxDistance, filters: $f) { name } }
}
"""
FILTERED = "query($f: DefinitionFilter){ definitions(filters: $f){ name } }"


@sync_to_async
def _definition(ctx: HttpContext, name: str, description: str = "", **kwargs) -> Definition:
    return Definition.objects.create(name=name, description=description, hash=uuid.uuid4().hex, organization=ctx.request.organization, **kwargs)


async def _pinned(ctx: HttpContext, name: str, anchor: np.ndarray, distance: float) -> Definition:
    """A definition whose vector sits exactly ``distance`` away from ``anchor``."""
    row = await _definition(ctx, name)
    await Definition.objects.filter(pk=row.pk).aupdate(embedding=_vec(anchor, distance), embedding_model=engine.model_id())
    return row


async def _anchor(ctx: HttpContext, name: str = "Anchor") -> tuple[Definition, np.ndarray]:
    row = await _definition(ctx, name, "Detect cells in an image")
    await row.arefresh_from_db()
    return row, np.asarray(row.embedding)


async def _similar(ctx: HttpContext, row: Definition, **variables) -> list[str]:
    data = await execute(SIMILAR, ctx, {"id": str(row.id), **variables})
    return [d["name"] for d in data["definition"]["similarDefinitions"]]


async def _names(ctx: HttpContext, filters: dict) -> list[str]:
    data = await execute(FILTERED, ctx, {"f": filters})
    return [d["name"] for d in data["definitions"]]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_similar_is_ordered_by_distance_and_excludes_itself(authenticated_context: HttpContext) -> None:
    row, e0 = await _anchor(authenticated_context)
    await _pinned(authenticated_context, "Far", e0, 0.6)
    await _pinned(authenticated_context, "Near", e0, 0.05)
    await _pinned(authenticated_context, "Mid", e0, 0.3)

    assert await _similar(authenticated_context, row) == ["Near", "Mid", "Far"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_similar_respects_limit_and_optional_max_distance(authenticated_context: HttpContext) -> None:
    row, e0 = await _anchor(authenticated_context)
    await _pinned(authenticated_context, "Near", e0, 0.05)
    await _pinned(authenticated_context, "Mid", e0, 0.3)
    await _pinned(authenticated_context, "Far", e0, 0.6)

    assert await _similar(authenticated_context, row, limit=2) == ["Near", "Mid"]
    # Without a maxDistance the far row still comes back; grouping is relative, not absolute.
    assert await _similar(authenticated_context, row, maxDistance=0.4) == ["Near", "Mid"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_similar_skips_unindexed_and_foreign_vectors(authenticated_context: HttpContext) -> None:
    """A NULL vector, or one from another model, has no comparable distance."""
    row, e0 = await _anchor(authenticated_context)
    await _pinned(authenticated_context, "Near", e0, 0.05)
    await Definition.objects.filter(pk=(await _pinned(authenticated_context, "Stale", e0, 0.01)).pk).aupdate(embedding_model="some-other-model")
    await _definition(authenticated_context, "", "")  # no text to index

    assert await _similar(authenticated_context, row) == ["Near"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_similar_never_crosses_organizations(
    authenticated_context: HttpContext,
    other_org_context: HttpContext,
) -> None:
    """The neighbourhood is prescoped like every other read of a definition."""
    row, e0 = await _anchor(authenticated_context)
    await _pinned(other_org_context, "Foreign neighbour", e0, 0.01)
    await _pinned(authenticated_context, "Own neighbour", e0, 0.2)

    assert await _similar(authenticated_context, row) == ["Own neighbour"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_similar_to_filter_groups_the_list_query(authenticated_context: HttpContext) -> None:
    row, e0 = await _anchor(authenticated_context)
    await _pinned(authenticated_context, "Near", e0, 0.05)
    await _pinned(authenticated_context, "Mid", e0, 0.3)

    names = await _names(authenticated_context, {"similarTo": str(row.id)})

    assert names == ["Near", "Mid"], "the anchor itself is not part of its own neighbourhood"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_similar_to_composes_with_other_filters(authenticated_context: HttpContext) -> None:
    """The point of the filter over the field: a neighbourhood narrowed by a facet."""
    row, e0 = await _anchor(authenticated_context)
    near = await _pinned(authenticated_context, "Near generator", e0, 0.05)
    await Definition.objects.filter(pk=near.pk).aupdate(kind="GENERATOR")
    await _pinned(authenticated_context, "Near function", e0, 0.1)

    assert await _names(authenticated_context, {"similarTo": str(row.id), "kinds": ["GENERATOR"]}) == ["Near generator"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_search_matches_the_description(authenticated_context: HttpContext) -> None:
    """A definition is found by what it says it does, not only by what it is called."""
    await _definition(authenticated_context, "Segment nuclei", "Finds every nucleus in a widefield stack")
    await _definition(authenticated_context, "Unrelated", "Writes a report")

    assert await _names(authenticated_context, {"search": "widefield"}) == ["Segment nuclei"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_facet_filters(authenticated_context: HttpContext) -> None:
    """Each new facet keeps exactly the rows it names."""
    collection = await Collection.objects.acreate(name="Imaging", organization=authenticated_context.request.organization)
    protocol = await Protocol.objects.acreate(name="Predicate", organization=authenticated_context.request.organization)

    kept = await _definition(authenticated_context, "Kept", "", kind="GENERATOR", scope="LOCAL", pure=True, idempotent=True, interfaces=["cellpose", "segmentation"])
    other = await _definition(authenticated_context, "Other", "", kind="FUNCTION", scope="GLOBAL", interfaces=["reporting"])
    await kept.collections.aadd(collection)
    await kept.protocols.aadd(protocol)
    await other.tests.aadd(kept)

    assert await _names(authenticated_context, {"kinds": ["GENERATOR"]}) == ["Kept"]
    assert await _names(authenticated_context, {"scopes": ["LOCAL"]}) == ["Kept"]
    assert await _names(authenticated_context, {"pure": True}) == ["Kept"]
    assert await _names(authenticated_context, {"idempotent": True}) == ["Kept"]
    assert await _names(authenticated_context, {"collections": [str(collection.id)]}) == ["Kept"]
    assert await _names(authenticated_context, {"protocols": [str(protocol.id)]}) == ["Kept"]
    assert await _names(authenticated_context, {"isTestFor": [str(other.id)]}) == ["Kept"]
    assert await _names(authenticated_context, {"hasTests": True}) == ["Other"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_interfaces_filter_demands_every_interface(authenticated_context: HttpContext) -> None:
    """`interfaces` is a JSONB list, so the filter must be containment of all terms, not any."""
    await _definition(authenticated_context, "Both", interfaces=["cellpose", "segmentation"])
    await _definition(authenticated_context, "One", interfaces=["segmentation"])

    assert sorted(await _names(authenticated_context, {"interfaces": ["segmentation"]})) == ["Both", "One"]
    assert await _names(authenticated_context, {"interfaces": ["cellpose", "segmentation"]}) == ["Both"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_defined_at_window(authenticated_context: HttpContext) -> None:
    old = await _definition(authenticated_context, "Old")
    new = await _definition(authenticated_context, "New")

    assert await _names(authenticated_context, {"definedAfter": new.defined_at.isoformat()}) == ["New"]
    assert await _names(authenticated_context, {"definedBefore": old.defined_at.isoformat()}) == ["Old"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_similar_to_will_not_read_another_orgs_anchor(
    authenticated_context: HttpContext,
    other_org_context: HttpContext,
) -> None:
    """The rows returned are scoped anyway -- but the anchor's *meaning* must not leak either.

    Reading the vector off another organization's definition would make this filter an
    oracle: "which of my definitions are close to that one", plus confirmation that the id
    exists at all.
    """
    foreign, e0 = await _anchor(other_org_context, "Foreign anchor")
    await _pinned(authenticated_context, "Mine", e0, 0.05)

    assert await _names(authenticated_context, {"similarTo": str(foreign.id)}) == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_many_to_many_filters_do_not_duplicate_rows(authenticated_context: HttpContext) -> None:
    """A join over a to-many relation repeats a row once per match unless it is deduped."""
    organization = authenticated_context.request.organization
    first = await Collection.objects.acreate(name="Imaging", organization=organization)
    second = await Collection.objects.acreate(name="Analysis", organization=organization)

    row = await _definition(authenticated_context, "In both")
    await row.collections.aadd(first, second)

    assert await _names(authenticated_context, {"collections": [str(first.id), str(second.id)]}) == ["In both"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_similar_to_does_not_cut_the_neighbourhood_off(authenticated_context: HttpContext) -> None:
    """A facet must reach past the tenth-nearest row.

    Ranking the whole comparable set rather than slicing the top ten is what makes this
    work: the only generator here sits at rank twelve, and a slice would answer "nothing
    like this exists" for a row that does.
    """
    row, e0 = await _anchor(authenticated_context)
    for index in range(12):
        await _pinned(authenticated_context, f"Function {index}", e0, 0.05 + index * 0.01)
    late = await _pinned(authenticated_context, "Late generator", e0, 0.4)
    await Definition.objects.filter(pk=late.pk).aupdate(kind="GENERATOR")

    assert await _names(authenticated_context, {"similarTo": str(row.id), "kinds": ["GENERATOR"]}) == ["Late generator"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_similar_to_and_search_together_rank_by_similarity(authenticated_context: HttpContext) -> None:
    """Both filters rank, so one of them has to win -- pin which, rather than leave it undefined.

    `similarTo` is applied after `search` and its ordering replaces the hybrid one. Asking
    for both means "among the definitions matching this text, the ones most like that row",
    which is the reading that makes the combination worth allowing at all.
    """
    row, e0 = await _anchor(authenticated_context)
    far = await _pinned(authenticated_context, "cells far", e0, 0.5)
    near = await _pinned(authenticated_context, "cells near", e0, 0.05)
    await Definition.objects.filter(pk__in=[far.pk, near.pk]).aupdate(description="about cells")

    assert await _names(authenticated_context, {"search": "cells", "similarTo": str(row.id)}) == ["cells near", "cells far"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_similar_to_an_unindexed_definition_is_empty(authenticated_context: HttpContext) -> None:
    """No vector on the anchor means no neighbourhood -- the same answer as an unknown id."""
    anchor = await _definition(authenticated_context, "", "")
    await _definition(authenticated_context, "Something else", "Detect cells in an image")

    assert await _names(authenticated_context, {"similarTo": str(anchor.id)}) == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_similar_definitions_takes_the_same_filters_as_the_list(authenticated_context: HttpContext) -> None:
    """`filters` on the field narrows the candidates, the way rekuest's `similarActions` does."""
    row, e0 = await _anchor(authenticated_context)
    generator = await _pinned(authenticated_context, "Near generator", e0, 0.05)
    await Definition.objects.filter(pk=generator.pk).aupdate(kind="GENERATOR")
    await _pinned(authenticated_context, "Nearer function", e0, 0.01)

    assert await _similar(authenticated_context, row, f={"kinds": ["GENERATOR"]}) == ["Near generator"]
