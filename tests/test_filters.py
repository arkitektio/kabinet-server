"""Tests for the migrated (non-deprecated) strawberry-django filter API and the related
server-bug fixes.

The filters in ``bridge/filters.py`` were ported from the deprecated
``filter_<field>(self, queryset, info)`` methods to ``@strawberry_django.filter_field``
resolvers. These tests drive the filters *through the schema* (``schema.execute``) like the
rest of the suite and cover:

* every list query still filters on its existing fields (``ids`` / ``search`` / the
  per-model custom fields), and
* the new logical-composition fields the migration unlocked (``AND`` / ``OR`` / ``NOT``).

They also pin the two server bugs that were fixed alongside the migration:

* org-scoped list queries no longer crash when ``filters`` is explicitly ``null``
  (previously ``'NoneType' object has no attribute 'get'`` in ``build_prescoped_queryset``),
  and
* ``declareResource`` accepts input without a ``name``.
"""

import pytest

from kante.context import HttpContext
from tests.test_pods import DECLARE_BACKEND, DECLARE_RESOURCE, setup_pod
from tests.utils import execute


# ---------------------------------------------------------------------------
# Bug fixes
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_null_filters_do_not_crash(authenticated_context: HttpContext, flavour_id: str) -> None:
    """Passing ``filters: null`` (the default the generated client sends) must not crash.

    The crash was server-side in ``build_prescoped_queryset``; the variable has to be named
    ``filters`` to reproduce the original lookup. Every org-scoped list query is covered.
    """
    await setup_pod(authenticated_context, flavour_id)

    cases = [
        ("backends", "BackendFilter"),
        ("resources", "ResourceFilter"),
        ("pods", "PodFilter"),
        ("githubRepos", "GithubRepoFilter"),
    ]
    for field, filter_type in cases:
        document = "query($filters: %s){ %s(filters: $filters){ id } }" % (filter_type, field)

        explicit_null = (await execute(document, authenticated_context, {"filters": None}))[field]
        assert len(explicit_null) >= 1, f"{field} with filters=null should still return rows"

        omitted = (await execute(document, authenticated_context))[field]
        assert [r["id"] for r in omitted] == [r["id"] for r in explicit_null], field


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_declare_resource_without_name(authenticated_context: HttpContext, flavour_id: str) -> None:
    """``declareResource`` must accept input with no ``name`` (optional in the client model)."""
    backend = (
        await execute(DECLARE_BACKEND, authenticated_context, {"input": {"name": "b", "kind": "docker"}})
    )["declareBackend"]

    resource = (
        await execute(
            DECLARE_RESOURCE,
            authenticated_context,
            {"input": {"backend": backend["id"], "localId": "res-noname"}},
        )
    )["declareResource"]

    assert resource["id"] is not None
    assert resource["resourceId"] == "res-noname"
    # No name supplied -> falls back to the model default rather than erroring.
    assert resource["name"] == "unset"


# ---------------------------------------------------------------------------
# Filter field migration — per-model custom fields
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_github_repo_custom_filter_fields(authenticated_context: HttpContext, built_chain: dict) -> None:
    """The GithubRepo ``repo`` / ``user`` / ``branch`` filters (migrated) each narrow correctly."""
    repo_id = built_chain["repo_id"]

    async def repo_ids(filters: dict) -> list[str]:
        hit = (
            await execute(
                "query($f: GithubRepoFilter){ githubRepos(filters: $f){ id } }",
                authenticated_context,
                {"f": filters},
            )
        )["githubRepos"]
        return [r["id"] for r in hit]

    assert await repo_ids({"repo": "om"}) == [repo_id]
    assert await repo_ids({"user": "arkitektio"}) == [repo_id]
    assert await repo_ids({"branch": "main"}) == [repo_id]
    assert await repo_ids({"ids": [repo_id]}) == [repo_id]
    assert await repo_ids({"branch": "nope"}) == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_pod_filter_backend_and_search(authenticated_context: HttpContext, flavour_id: str) -> None:
    """PodFilter ``backend`` (backend__id) and ``search`` (backend__name) both work."""
    setup = await setup_pod(authenticated_context, flavour_id)
    pod_id, backend_id = setup["pod"]["id"], setup["backend"]["id"]

    by_backend = (
        await execute(
            "query($f: PodFilter){ pods(filters: $f){ id } }",
            authenticated_context,
            {"f": {"backend": backend_id}},
        )
    )["pods"]
    assert [p["id"] for p in by_backend] == [pod_id]

    by_name = (
        await execute(
            "query($f: PodFilter){ pods(filters: $f){ id } }",
            authenticated_context,
            {"f": {"search": "my-backend"}},
        )
    )["pods"]
    assert [p["id"] for p in by_name] == [pod_id]

    miss = (
        await execute(
            "query($f: PodFilter){ pods(filters: $f){ id } }",
            authenticated_context,
            {"f": {"search": "other-backend"}},
        )
    )["pods"]
    assert miss == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_flavour_has_definitions_filter(authenticated_context: HttpContext, flavour_id: str) -> None:
    """FlavourFilter.has_definitions (definitions__in) keeps flavours providing a definition."""
    definitions = (await execute("query{ definitions{ id } }", authenticated_context))["definitions"]
    definition_id = definitions[0]["id"]

    hit = (
        await execute(
            "query($f: FlavourFilter){ flavours(filters: $f){ id } }",
            authenticated_context,
            {"f": {"hasDefinitions": [definition_id]}},
        )
    )["flavours"]
    assert flavour_id in [f["id"] for f in hit]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_definition_demands_filter_is_wired(authenticated_context: HttpContext, built_chain: dict) -> None:
    """The complex DefinitionFilter.demands resolver is reachable via the new API.

    An empty ``demands`` list exercises the resolver without constraining (no demands ->
    no id restriction), proving the migrated method runs end-to-end without error.
    """
    definitions = (
        await execute(
            "query($f: DefinitionFilter){ definitions(filters: $f){ id } }",
            authenticated_context,
            {"f": {"demands": []}},
        )
    )["definitions"]
    assert len(definitions) == 1


# ---------------------------------------------------------------------------
# Filter field migration — new logical composition (AND / OR / NOT)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_filter_logical_composition(authenticated_context: HttpContext, built_chain: dict) -> None:
    """The new filter API adds AND/OR/NOT composition over the migrated fields."""
    repo_id = built_chain["repo_id"]

    async def repo_ids(filters: dict) -> list[str]:
        hit = (
            await execute(
                "query($f: GithubRepoFilter){ githubRepos(filters: $f){ id } }",
                authenticated_context,
                {"f": filters},
            )
        )["githubRepos"]
        return [r["id"] for r in hit]

    # AND: the top-level field and the nested AND filter must both match.
    assert await repo_ids({"user": "arkitektio", "AND": {"branch": "main"}}) == [repo_id]
    assert await repo_ids({"user": "arkitektio", "AND": {"branch": "nope"}}) == []

    # OR: either the top-level field or the nested OR filter matching is enough.
    assert await repo_ids({"repo": "ome", "OR": {"repo": "nope"}}) == [repo_id]
    assert await repo_ids({"repo": "nope", "OR": {"repo": "still-nope"}}) == []

    # NOT: inverts the nested match.
    assert await repo_ids({"NOT": {"repo": "nope"}}) == [repo_id]
    assert await repo_ids({"NOT": {"repo": "ome"}}) == []
