"""Bloks a GitHub repository publishes on its own, in ``.arkitekt/bloks.yaml``.

A repository may publish app images, bloks, or both; either file is enough to track it. Each
blok's BSX is in a file of the repository or written inline, and is read in the same scan. The
fetch cases run against a real HTTP server standing in for ``raw.githubusercontent.com``, like
``test_repo_inspection``; the write cases against the database.
"""

from pathlib import Path

import pytest
import yaml
from asgiref.sync import sync_to_async
from kante.context import HttpContext

from bridge import models
from bridge.repo import layout
from bridge.repo.db import apply_contents
from bridge.repo.fetch import InspectionError, RepoContents, aget_repo_contents
from tests.test_repo_inspection import COORDINATES, fake_github  # noqa: F401 - the fixture
from tests.utils import build_relative_dir, execute

VALID_CONFIG = Path(build_relative_dir("deployments/deployments.yaml")).read_text()

PANEL = "<Html><Card><Text>Layers</Text></Card></Html>"
SCENE = '<Scene id="volume" persist />'
BROKEN = "<Html><Card><Text></Card></Html>"


def bloks_file(*bloks: dict) -> str:
    return yaml.safe_dump({"spec_version": 1, "bloks": list(bloks)})


LAYERS = {"key": "layers", "vocab": 2, "name": "Layer picker", "description": "Pick the visible layers", "source": "bloks/layers.bsx"}
VOLUME = {"key": "volume", "vocab": 2, "name": "Volume", "context": "SCENE", "bsx": SCENE, "demo": {"args": {"z": 1}}}


@pytest.mark.asyncio
async def test_a_repository_with_only_bloks_scans(fake_github):
    coordinates = await fake_github({layout.BLOKS_PATH: bloks_file(LAYERS, VOLUME), "bloks/layers.bsx": PANEL})

    contents = await aget_repo_contents(coordinates)

    assert contents.config is None
    assert [(blok.declaration.key, blok.source) for blok in contents.bloks] == [("layers", PANEL), ("volume", SCENE)]


@pytest.mark.asyncio
async def test_a_repository_with_both_reads_both(fake_github):
    coordinates = await fake_github({layout.DEPLOYMENTS_PATH: VALID_CONFIG, layout.BLOKS_PATH: bloks_file(VOLUME)})

    contents = await aget_repo_contents(coordinates)

    assert contents.config.app_images
    assert [blok.declaration.key for blok in contents.bloks] == ["volume"]


@pytest.mark.asyncio
async def test_a_repository_with_neither_says_both_files(fake_github):
    coordinates = await fake_github({"README.md": "# ome\n"})

    with pytest.raises(InspectionError) as excinfo:
        await aget_repo_contents(coordinates)

    message = str(excinfo.value)
    assert "no `.arkitekt/` folder" in message
    assert layout.BLOKS_PATH in message


@pytest.mark.asyncio
async def test_a_missing_source_file_names_the_blok(fake_github):
    coordinates = await fake_github({layout.BLOKS_PATH: bloks_file(LAYERS)})

    with pytest.raises(InspectionError, match=r"'layers' names `bloks/layers.bsx`"):
        await aget_repo_contents(coordinates)


@pytest.mark.asyncio
async def test_a_source_outside_the_repository_is_refused(fake_github):
    coordinates = await fake_github({layout.BLOKS_PATH: bloks_file({**LAYERS, "source": "../secrets.bsx"})})

    with pytest.raises(InspectionError, match="not a path inside the repository"):
        await aget_repo_contents(coordinates)


@pytest.mark.asyncio
async def test_a_blok_names_one_source(fake_github):
    coordinates = await fake_github({layout.BLOKS_PATH: bloks_file({**LAYERS, "bsx": PANEL}), "bloks/layers.bsx": PANEL})

    with pytest.raises(InspectionError, match="exactly one of `source`"):
        await aget_repo_contents(coordinates)


@pytest.mark.asyncio
async def test_a_logo_is_not_published_on_its_own(fake_github):
    coordinates = await fake_github({layout.BLOKS_PATH: bloks_file({**VOLUME, "context": "LOGO"})})

    with pytest.raises(InspectionError, match="panels \\(HTML\\) and scenes"):
        await aget_repo_contents(coordinates)


@pytest.mark.asyncio
async def test_keys_are_unique(fake_github):
    coordinates = await fake_github({layout.BLOKS_PATH: bloks_file(VOLUME, VOLUME)})

    with pytest.raises(InspectionError, match="used by more than one blok"):
        await aget_repo_contents(coordinates)


@sync_to_async
def _repo(ctx: HttpContext) -> models.GithubRepo:
    repo, _ = models.GithubRepo.objects.get_or_create(
        user=COORDINATES.user, repo=COORDINATES.repo, branch=COORDINATES.branch, organization=ctx.request.organization, defaults=dict(name=str(COORDINATES))
    )
    return repo


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_scan_writes_its_bloks_by_key_and_drops_the_rest(fake_github, authenticated_context: HttpContext):
    organization = authenticated_context.request.organization
    repo = await _repo(authenticated_context)
    coordinates = await fake_github({layout.BLOKS_PATH: bloks_file(LAYERS, {**VOLUME, "bsx": BROKEN, "context": "HTML"}), "bloks/layers.bsx": PANEL})

    await sync_to_async(apply_contents)(await aget_repo_contents(coordinates), repo, organization)
    first = {blok.key: blok async for blok in models.RepoBlok.objects.filter(repo=repo)}

    assert set(first) == {"layers", "volume"}
    assert first["layers"].component_tree and first["layers"].parse_error is None
    # One broken blok is the blok's problem, not the scan's.
    assert first["volume"].component_tree is None and first["volume"].parse_error

    await sync_to_async(apply_contents)(RepoContents(None, (await aget_repo_contents(coordinates)).bloks[:1]), repo, organization)
    second = [blok async for blok in models.RepoBlok.objects.filter(repo=repo)]

    assert [(blok.key, blok.id) for blok in second] == [("layers", first["layers"].id)]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_blok_says_how_rekuest_installs_it(fake_github, authenticated_context: HttpContext):
    repo = await _repo(authenticated_context)
    dependency = {"key": "viewer", "app": "napari", "action_dependencies": [{"key": "open", "demand": {"key": "open_image", "app": "napari"}}]}
    coordinates = await fake_github(
        {layout.BLOKS_PATH: bloks_file({**LAYERS, "dependencies": [dependency], "demo": {"args": {"layer_names": ["a"]}}, "locals": [{"key": "show_all", "kind": "BOOL", "default": True, "persist": True}], "catalogs": ["ui@1"], "module": "orkestrator"}), "bloks/layers.bsx": PANEL}
    )
    await sync_to_async(apply_contents)(await aget_repo_contents(coordinates), repo, authenticated_context.request.organization)

    result = await execute(
        """
        query { repoBloks { key origin hash installHash context installInput repo { id } } }
        """,
        authenticated_context,
    )

    [blok] = result["repoBloks"]
    assert blok["origin"] == f"github:{COORDINATES.user}/{COORDINATES.repo}:{COORDINATES.branch}#layers"
    assert blok["context"] == "HTML"
    install = blok["installInput"]
    assert install["name"] == "Layer picker"
    assert install["source"] == PANEL
    assert install["origin"] == blok["origin"]
    assert install["originHash"] == blok["installHash"]
    # rekuest's input is camelCase, and leaves out what is not set.
    assert install["dependencies"][0]["actionDependencies"][0]["demand"] == {"key": "open_image", "app": "napari"}
    assert "forModel" not in install
    # A demo is the blok's data: its keys are what the blok reads, so they stay as written.
    assert install["vocab"] == 2
    assert install["demo"] == {"args": {"layer_names": ["a"]}}
    assert install["locals"] == [{"key": "show_all", "kind": "BOOL", "nullable": False, "default": True, "persist": True}]
    assert install["catalogs"] == ["ui@1"]
    assert install["module"] == "orkestrator"


INSTALL_HASH = "query { repoBloks { hash installHash } }"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_change_to_anything_installed_is_an_update(fake_github, authenticated_context: HttpContext):
    """Its dependencies are not drawn, so `hash` stays; what installing writes changed, so `installHash` does not."""
    organization = authenticated_context.request.organization
    repo = await _repo(authenticated_context)

    async def scan(blok: dict) -> dict:
        coordinates = await fake_github({layout.BLOKS_PATH: bloks_file(blok), "bloks/layers.bsx": PANEL})
        await sync_to_async(apply_contents)(await aget_repo_contents(coordinates), repo, organization)
        return (await execute(INSTALL_HASH, authenticated_context))["repoBloks"][0]

    before = await scan(LAYERS)
    after = await scan({**LAYERS, "dependencies": [{"key": "viewer", "app": "napari"}]})

    assert after["hash"] == before["hash"]
    assert after["installHash"] != before["installHash"]


@pytest.mark.asyncio
async def test_a_blok_speaks_blok_language_v2(fake_github):
    for blok, message in [
        ({key: value for key, value in VOLUME.items() if key != "vocab"}, "vocab"),
        ({**VOLUME, "vocab": 1}, "vocab"),
        ({**VOLUME, "demo_state": {"z": 1}}, "demo_state"),
        ({**VOLUME, "locals": [{"key": "task", "kind": "STRING"}]}, r"\[roots\.reserved\]"),
        ({**VOLUME, "catalogs": ["ui"]}, r"\[manifest\.catalog\]"),
    ]:
        coordinates = await fake_github({layout.BLOKS_PATH: bloks_file(blok)})
        with pytest.raises(InspectionError, match=message):
            await aget_repo_contents(coordinates)
