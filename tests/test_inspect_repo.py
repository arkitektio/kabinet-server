"""``createGithubRepo`` end to end, against a stubbed manifest fetch.

This used to hit raw.githubusercontent.com for real -- the only test in the suite that
touched the network, against the invariant the rest of it states (see the module
docstring of ``tests/test_pods.py``). It has been failing for a while and not because of
anything in this repo: ``arkitektio-apps/ome`` still exists but no longer publishes
``.arkitekt_next/deployments.yaml``, so the fetch 404s and a third party decides whether
CI is green.

The manifest fetch is stubbed with the checked-in fixture instead, which is what the test
was actually trying to exercise: identifier parsing, repo creation and the catalogue walk.
"""

import pytest
import yaml
from kante.context import HttpContext

from tests.utils import build_relative_dir, execute

CREATE_GITHUB_REPO = """
    mutation CreateGithubRepo($input: CreateGithubRepoInput!) {
        createGithubRepo(input: $input) {
            id
            user
            repo
            branch
            url
            flavours { id name }
        }
    }
"""


@pytest.fixture
def stub_manifest(monkeypatch):
    """Serve the checked-in deployments.yaml instead of fetching one over HTTP."""
    from bridge.mutations import repo as repo_mutations
    from bridge.repo.models import KabinetConfigFile

    with open(build_relative_dir("deployments/deployments.yaml")) as f:
        config = KabinetConfigFile(**yaml.safe_load(f))

    async def fake_fetch(kabinet_url: str) -> KabinetConfigFile:
        return config

    monkeypatch.setattr(repo_mutations, "aget_kabinet_config", fake_fetch)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_github_repo(authenticated_context: HttpContext, stub_manifest):
    """Tracking a repo by identifier creates it and populates its flavours."""
    assert authenticated_context.request.organization is not None, "Organization should be set"

    repo = (
        await execute(CREATE_GITHUB_REPO, authenticated_context, {"input": {"identifier": "arkitektio-apps/ome"}})
    )["createGithubRepo"]

    assert repo["id"] is not None
    assert (repo["user"], repo["repo"], repo["branch"]) == ("arkitektio-apps", "ome", "main")
    assert repo["url"] == "https://github.com/arkitektio-apps/ome"
    assert repo["flavours"], "scanning the manifest should have produced flavours"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_github_repo_accepts_a_url_with_a_branch(authenticated_context: HttpContext, stub_manifest):
    """A full GitHub URL with a /tree/<branch> suffix resolves to that branch.

    ``infer_repo_info`` used to validate this input with ``assert`` -- stripped under
    ``python -O`` -- and returned a different meaning in the name slot depending on which
    branch of it ran.
    """
    repo = (
        await execute(
            CREATE_GITHUB_REPO,
            authenticated_context,
            {"input": {"identifier": "https://github.com/arkitektio-apps/ome/tree/dev"}},
        )
    )["createGithubRepo"]

    assert (repo["user"], repo["repo"], repo["branch"]) == ("arkitektio-apps", "ome", "dev")


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_github_repo_rejects_a_bare_word(authenticated_context: HttpContext, stub_manifest):
    """An identifier that names no repository is refused, not guessed at."""
    from tests.utils import execute_raw

    result = await execute_raw(CREATE_GITHUB_REPO, authenticated_context, {"input": {"identifier": "not-an-identifier"}})

    assert result.errors, "a malformed identifier should be an error"
