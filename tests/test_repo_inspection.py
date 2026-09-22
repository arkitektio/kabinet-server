"""What kabinet says when a repository cannot be read.

Every case runs against a real HTTP server standing in for ``raw.githubusercontent.com``
-- serving a fake repository tree -- rather than a mocked ``aiohttp``. The whole point of
these messages is what a real 404 on one path plus a real 200 on a sibling adds up to, and
a mock that returns whatever it was told cannot get that wrong.
"""

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio
import yaml
from aiohttp import web

from bridge.repo import fetch, layout
from bridge.repo.fetch import InspectionError, RepoCoordinates, aget_kabinet_config
from tests.utils import build_relative_dir, execute_raw

COORDINATES = RepoCoordinates("arkitektio-apps", "ome", "main")

VALID_CONFIG = Path(build_relative_dir("deployments/deployments.yaml")).read_text()


@pytest_asyncio.fixture
async def fake_github(monkeypatch):
    """Serve a dict of ``{repo path: body or status}`` as if it were the raw file host."""

    async def serve(tree: dict[str, object], handler=None) -> RepoCoordinates:
        async def handle(request: web.Request) -> web.Response:
            # /<user>/<repo>/<branch>/<path...>
            path = "/".join(request.match_info["tail"].split("/"))
            entry = tree.get(path)
            if entry is None:
                raise web.HTTPNotFound()
            if isinstance(entry, int):
                return web.Response(status=entry)
            return web.Response(text=entry)

        app = web.Application()
        app.router.add_get("/{user}/{repo}/{branch}/{tail:.*}", handler or handle)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        servers.append(runner)
        port = runner.addresses[0][1]
        monkeypatch.setattr(layout, "RAW_BASE", f"http://127.0.0.1:{port}")
        return COORDINATES

    servers: list[web.AppRunner] = []
    yield serve
    for runner in servers:
        await runner.cleanup()


async def inspect(coordinates: RepoCoordinates) -> None:
    await aget_kabinet_config(layout.raw_url(*coordinates, layout.DEPLOYMENTS_PATH), coordinates)


@pytest.mark.asyncio
async def test_legacy_folder_is_named_in_the_error(fake_github):
    """The folder was renamed from `.arkitekt_next` -- say so instead of "not an Arkitekt repo"."""
    coordinates = await fake_github({".arkitekt_next/deployments.yaml": VALID_CONFIG})

    with pytest.raises(InspectionError) as excinfo:
        await inspect(coordinates)

    message = str(excinfo.value)
    assert ".arkitekt_next/deployments.yaml" in message
    assert ".arkitekt" in message
    assert "rename" in message.lower()


@pytest.mark.asyncio
async def test_hyphenated_legacy_folder_is_also_recognised(fake_github):
    coordinates = await fake_github({".arkitekt-next/deployments.yaml": VALID_CONFIG})

    with pytest.raises(InspectionError, match=r"\.arkitekt-next/deployments\.yaml"):
        await inspect(coordinates)


@pytest.mark.asyncio
async def test_config_folder_without_deployments(fake_github):
    """The case the rename does not explain: the folder is there, the file is not."""
    coordinates = await fake_github({".arkitekt/manifest.yaml": "identifier: test\n"})

    with pytest.raises(InspectionError) as excinfo:
        await inspect(coordinates)

    message = str(excinfo.value)
    assert ".arkitekt/deployments.yaml" in message
    assert "app images are built" in message


@pytest.mark.asyncio
async def test_repo_without_any_config_folder(fake_github):
    coordinates = await fake_github({"README.md": "# ome\n"})

    with pytest.raises(InspectionError) as excinfo:
        await inspect(coordinates)

    message = str(excinfo.value)
    assert "no `.arkitekt/` folder" in message
    assert "main" in message


@pytest.mark.asyncio
async def test_unreachable_repo_says_so(fake_github):
    coordinates = await fake_github({})

    with pytest.raises(InspectionError, match="not even a README"):
        await inspect(coordinates)


@pytest.mark.asyncio
async def test_private_repo_or_rate_limit(fake_github):
    coordinates = await fake_github({layout.DEPLOYMENTS_PATH: 403})

    with pytest.raises(InspectionError, match="private repository, or GitHub rate-limiting"):
        await inspect(coordinates)


@pytest.mark.asyncio
async def test_github_outage(fake_github):
    coordinates = await fake_github({layout.DEPLOYMENTS_PATH: 502})

    with pytest.raises(InspectionError, match="outage on their side"):
        await inspect(coordinates)


@pytest.mark.asyncio
async def test_empty_config(fake_github):
    coordinates = await fake_github({layout.DEPLOYMENTS_PATH: "\n  \n"})

    with pytest.raises(InspectionError, match="exists but is empty"):
        await inspect(coordinates)


@pytest.mark.asyncio
async def test_malformed_yaml_points_at_the_line(fake_github):
    coordinates = await fake_github({layout.DEPLOYMENTS_PATH: "app_images:\n  - name: one\n   bad indent: yes\n"})

    with pytest.raises(InspectionError) as excinfo:
        await inspect(coordinates)

    message = str(excinfo.value)
    assert "not valid YAML" in message
    assert "line 3" in message


@pytest.mark.asyncio
async def test_yaml_that_is_not_a_mapping(fake_github):
    coordinates = await fake_github({layout.DEPLOYMENTS_PATH: "- one\n- two\n"})

    with pytest.raises(InspectionError, match="contains a list, not a mapping"):
        await inspect(coordinates)


@pytest.mark.asyncio
async def test_invalid_config_lists_every_field(fake_github):
    """A pydantic ValidationError traceback is not an error message for a repo owner."""
    broken = yaml.safe_load(VALID_CONFIG)
    del broken["app_images"][0]["manifest"]["version"]
    broken["app_images"][0]["image"] = {}

    coordinates = await fake_github({layout.DEPLOYMENTS_PATH: yaml.safe_dump(broken)})

    with pytest.raises(InspectionError) as excinfo:
        await inspect(coordinates)

    message = str(excinfo.value)
    assert "is not a valid kabinet deployments file" in message
    assert "app_images.0.manifest.version" in message


@pytest.mark.asyncio
async def test_config_without_app_images(fake_github):
    """Valid, parseable, and describes nothing -- which used to be reported as success."""
    coordinates = await fake_github({layout.DEPLOYMENTS_PATH: "latest_app_image: null\n"})

    with pytest.raises(InspectionError, match="lists no app images"):
        await inspect(coordinates)


@pytest.mark.asyncio
async def test_a_good_config_still_parses(fake_github):
    coordinates = await fake_github({layout.DEPLOYMENTS_PATH: VALID_CONFIG})

    config = await aget_kabinet_config(layout.raw_url(*coordinates, layout.DEPLOYMENTS_PATH), coordinates)

    assert config.app_images


@pytest.mark.asyncio
async def test_slow_diagnosis_is_not_reported_as_a_timeout(fake_github, monkeypatch):
    """A slow diagnosis must not be reported as a timed-out fetch.

    The probes get their own budget (``DIAGNOSIS_TIMEOUT_SECONDS``) and run after the
    failed response is closed, so spending time on them cannot turn a clean, fast 404
    into "fetching took longer than Ns" -- a different, and wrong, story about the repo.
    """

    async def slow(request: web.Request) -> web.Response:
        await asyncio.sleep(0.4)
        raise web.HTTPNotFound()

    coordinates = await fake_github({}, handler=slow)
    monkeypatch.setattr(fetch, "FETCH_TIMEOUT_SECONDS", 1)

    with pytest.raises(InspectionError) as excinfo:
        await inspect(coordinates)

    assert "took longer than" not in str(excinfo.value)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_github_repo_surfaces_the_diagnosis(fake_github, authenticated_context):
    """The wiring: the real fetcher, called through the mutation, with real coordinates."""
    await fake_github({".arkitekt_next/deployments.yaml": VALID_CONFIG})

    result = await execute_raw(
        """
        mutation CreateGithubRepo($input: CreateGithubRepoInput!) {
            createGithubRepo(input: $input) { id }
        }
        """,
        authenticated_context,
        {"input": {"identifier": f"{COORDINATES.user}/{COORDINATES.repo}"}},
    )

    assert result.errors, "A repo publishing the pre-rename folder must not scan clean"
    message = str(result.errors[0].message)
    assert ".arkitekt_next/deployments.yaml" in message
    assert "rename" in message.lower()
