"""Cross-tenant isolation tests.

Every read is prescoped to the request's organization: list queries hide other
orgs' rows (``get_queryset`` -> ``build_prescoped_queryset``) and single-object
queries refuse to resolve another org's row by ID (``get_for_org`` raises
``DoesNotExist``, surfacing as a GraphQL error / null field).

Data is built in the ``authenticated_context`` org (``static_org``) and then read
back through ``other_org_context`` (``other_org``), which must see nothing.
"""

import pytest

from kante.context import HttpContext
from tests.utils import execute
from tests.test_pods import setup_pod


async def _execute_raw(query: str, context: HttpContext, variables: dict | None = None):
    """Execute without asserting success, so we can inspect cross-org errors/null."""
    from kabinet_server.schema import schema

    return await schema.execute(query, variable_values=variables or {}, context_value=context)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_list_queries_hide_other_orgs(
    authenticated_context: HttpContext,
    other_org_context: HttpContext,
    built_chain: dict,
    flavour_id: str,
) -> None:
    """Catalog + infra list queries return the owner org's rows and nothing for another org."""
    # Build the infra chain (backend/deployment/resource/pod) in the owner org.
    await setup_pod(authenticated_context, flavour_id)

    list_fields = (
        "githubRepos",
        "releases",
        "flavours",
        "definitions",
        "deployments",
        "backends",
        "pods",
        "resources",
    )

    for field in list_fields:
        query = "query{ %s { id } }" % field

        mine = (await execute(query, authenticated_context))[field]
        assert len(mine) >= 1, f"{field} should be visible to its own org"

        theirs = (await execute(query, other_org_context))[field]
        assert theirs == [], f"{field} must not leak to another org"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_single_object_queries_are_isolated(
    authenticated_context: HttpContext,
    other_org_context: HttpContext,
    built_chain: dict,
    flavour_id: str,
) -> None:
    """Fetching another org's row by ID must error instead of leaking it."""
    setup = await setup_pod(authenticated_context, flavour_id)

    repo_id = built_chain["repo_id"]
    release_id = (await execute("query{ releases{ id } }", authenticated_context))["releases"][0]["id"]
    definition_id = (await execute("query{ definitions{ id } }", authenticated_context))["definitions"][0]["id"]

    cases = [
        ("githubRepo", repo_id),
        ("release", release_id),
        ("flavour", flavour_id),
        ("definition", definition_id),
        ("backend", setup["backend"]["id"]),
        ("deployment", setup["deployment"]["id"]),
        ("resource", setup["resource"]["id"]),
        ("pod", setup["pod"]["id"]),
    ]

    for field, obj_id in cases:
        query = "query($id: ID!){ %s(id: $id){ id } }" % field

        # The owner org resolves the object fine.
        owner = await _execute_raw(query, authenticated_context, {"id": obj_id})
        assert not owner.errors, (field, owner.errors)
        assert owner.data[field]["id"] == obj_id

        # The other org cannot: the resolver raises DoesNotExist -> error + null field.
        other = await _execute_raw(query, other_org_context, {"id": obj_id})
        assert other.errors, f"{field} leaked a row to another org (no error raised)"
