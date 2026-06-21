"""GraphQL query tests for the catalog models (GithubRepo / Release / Flavour /
Definition), exercising the list queries together with their `filters` and `ordering`
inputs. All data is built offline via the `built_chain` fixture (see conftest) — no
external HTTP — and every assertion goes through `schema.execute` like the other tests.
"""

import pytest

from kante.context import HttpContext
from tests.utils import execute


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_github_repos_query_filter_order(authenticated_context: HttpContext, built_chain: dict) -> None:
    repo_id = built_chain["repo_id"]

    repos = (await execute("query{ githubRepos{ id repo user branch } }", authenticated_context))["githubRepos"]
    assert [r["id"] for r in repos] == [repo_id]
    assert repos[0]["repo"] == "ome"
    assert repos[0]["user"] == "arkitektio-apps"
    assert repos[0]["branch"] == "main"

    # filters: search hits the repo name; the dedicated repo/user/branch filters narrow too.
    for variables in ({"search": "ome"}, {"repo": "om"}, {"user": "arkitektio"}, {"branch": "main"}, {"ids": [repo_id]}):
        hit = (
            await execute(
                "query($f: GithubRepoFilter){ githubRepos(filters: $f){ id } }",
                authenticated_context,
                {"f": variables},
            )
        )["githubRepos"]
        assert [r["id"] for r in hit] == [repo_id], variables

    # a non-matching filter returns nothing.
    miss = (
        await execute(
            "query($f: GithubRepoFilter){ githubRepos(filters: $f){ id } }",
            authenticated_context,
            {"f": {"repo": "does-not-exist"}},
        )
    )["githubRepos"]
    assert miss == []

    # ordering input is accepted and returns the row.
    ordered = (
        await execute(
            "query($o: [GithubRepoOrder!]){ githubRepos(ordering: $o){ id } }",
            authenticated_context,
            {"o": [{"addedAt": "DESC"}]},
        )
    )["githubRepos"]
    assert [r["id"] for r in ordered] == [repo_id]

    # single-object query.
    one = (await execute("query($id: ID!){ githubRepo(id: $id){ id repo } }", authenticated_context, {"id": repo_id}))["githubRepo"]
    assert one["repo"] == "ome"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_releases_query_filter_order(authenticated_context: HttpContext, built_chain: dict) -> None:
    releases = (await execute("query{ releases{ id version } }", authenticated_context))["releases"]
    assert len(releases) == 1
    release_id = releases[0]["id"]
    assert releases[0]["version"] == "0.1.9"

    filtered = (
        await execute(
            "query($f: ReleaseFilter){ releases(filters: $f){ id } }",
            authenticated_context,
            {"f": {"search": "0.1"}},
        )
    )["releases"]
    assert [r["id"] for r in filtered] == [release_id]

    ordered = (
        await execute(
            "query($o: [ReleaseOrder!]){ releases(ordering: $o){ id } }",
            authenticated_context,
            {"o": [{"version": "ASC"}]},
        )
    )["releases"]
    assert [r["id"] for r in ordered] == [release_id]

    one = (await execute("query($id: ID!){ release(id: $id){ id version } }", authenticated_context, {"id": release_id}))["release"]
    assert one["version"] == "0.1.9"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_flavours_query_filter_order(authenticated_context: HttpContext, flavour_id: str) -> None:
    flavours = (await execute("query{ flavours{ id name } }", authenticated_context))["flavours"]
    assert flavour_id in [f["id"] for f in flavours]
    assert any(f["name"] == "vanilla" for f in flavours)

    filtered = (
        await execute(
            "query($f: FlavourFilter){ flavours(filters: $f){ id } }",
            authenticated_context,
            {"f": {"search": "vanilla"}},
        )
    )["flavours"]
    assert [f["id"] for f in filtered] == [flavour_id]

    # FlavourOrder exposes the custom released_at ordering.
    ordered = (
        await execute(
            "query($o: [FlavourOrder!]){ flavours(ordering: $o){ id } }",
            authenticated_context,
            {"o": [{"releasedAt": "DESC"}]},
        )
    )["flavours"]
    assert flavour_id in [f["id"] for f in ordered]

    one = (await execute("query($id: ID!){ flavour(id: $id){ id name } }", authenticated_context, {"id": flavour_id}))["flavour"]
    assert one["name"] == "vanilla"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_definitions_query_filter_order(authenticated_context: HttpContext, built_chain: dict) -> None:
    definitions = (await execute("query{ definitions{ id name hash } }", authenticated_context))["definitions"]
    assert len(definitions) == 1
    definition = definitions[0]
    assert definition["name"] == "Convert Omero"
    assert definition["hash"]

    filtered = (
        await execute(
            "query($f: DefinitionFilter){ definitions(filters: $f){ id } }",
            authenticated_context,
            {"f": {"search": "Omero"}},
        )
    )["definitions"]
    assert [d["id"] for d in filtered] == [definition["id"]]

    ordered = (
        await execute(
            "query($o: [DefinitionOrder!]){ definitions(ordering: $o){ id } }",
            authenticated_context,
            {"o": [{"definedAt": "DESC"}]},
        )
    )["definitions"]
    assert [d["id"] for d in ordered] == [definition["id"]]

    one = (await execute("query($id: ID!){ definition(id: $id){ id name } }", authenticated_context, {"id": definition["id"]}))["definition"]
    assert one["name"] == "Convert Omero"
