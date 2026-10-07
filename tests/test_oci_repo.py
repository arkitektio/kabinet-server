"""Importing an OCI repository: what kabinet takes from a registry, and what it refuses.

Every case runs against a real HTTP server standing in for a registry -- behind the token
challenge real registries answer anonymous reads with -- rather than a mocked ``aiohttp``.
What is under test is the sum of several requests (tags, manifests, blobs), and which of
them a second scan no longer makes.
"""

import copy
import hashlib
import json

import pytest
import pytest_asyncio
import yaml
from aiohttp import web
from asgiref.sync import sync_to_async
from kante.context import HttpContext

from bridge import models
from bridge.repo.oci import RELEASE_MEDIA_TYPE
from kabinet_server.hook_agent import rescan_sources
from tests.utils import build_relative_dir, execute, execute_raw

IMPORT = """
    mutation Import($input: ImportRepoInput!) {
        importRepo(input: $input) {
            id
            reference
            channels
            flavours { name image { imageString } source { reference } release { version channel revision digestPinned app { identifier } } }
        }
    }
"""


def _digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


class FakeRegistry:
    """Repositories of tags and blobs, served the way a registry serves anonymous readers."""

    def __init__(self) -> None:
        self.manifests: dict[str, dict[str, bytes]] = {}
        self.blobs: dict[str, bytes] = {}
        self.requests: list[str] = []
        self.host = ""

    def reference(self, repository: str) -> str:
        return f"{self.host}/{repository}"

    def image(self, repository: str, tag: str) -> str:
        """Push something that is an image, not a release; return its pinned reference."""
        manifest = json.dumps({"schemaVersion": 2, "manifests": [], "annotations": {"tag": tag}}).encode()
        self.manifests.setdefault(repository, {})[tag] = manifest
        return f"{self.reference(repository)}@{_digest(manifest)}"

    def release(self, repository: str, tag: str, version: str, *, channel: str | None = None, identifier: str = "ome", image: str | None = None) -> None:
        """Push a release descriptor under a tag, with one flavour whose image sits beside it."""
        with open(build_relative_dir("deployments/deployments.yaml")) as f:
            app_image = copy.deepcopy(yaml.safe_load(f)["app_images"][0])
        descriptor = {
            "spec_version": 1,
            "manifest": {**app_image["manifest"], "identifier": identifier, "version": version},
            "channel": channel,
            "revision": "3f2a9c1",
            "flavours": [
                {
                    "name": "vanilla",
                    "image": image or self.image(repository, f"{version}-vanilla"),
                    "selectors": app_image["selectors"],
                    "inspection": app_image["inspection"],
                }
            ],
        }
        blob = json.dumps(descriptor).encode()
        self.blobs[_digest(blob)] = blob
        config = {"mediaType": RELEASE_MEDIA_TYPE, "digest": _digest(blob), "size": len(blob)}
        manifest = json.dumps({"schemaVersion": 2, "config": config, "layers": [config]}).encode()
        self.manifests.setdefault(repository, {})[tag] = manifest

    def fetched(self, kind: str) -> list[str]:
        return [path for path in self.requests if f"/{kind}/" in path]

    async def handle(self, request: web.Request) -> web.Response:
        if request.path == "/token":
            return web.json_response({"token": "anonymous"})
        if request.headers.get("Authorization") != "Bearer anonymous":
            challenge = f'Bearer realm="http://{request.host}/token",service="fake",scope="repository:x:pull"'
            return web.Response(status=401, headers={"WWW-Authenticate": challenge})
        self.requests.append(request.path)
        repository, kind, reference = request.match_info["repository"], request.match_info["kind"], request.match_info["reference"]
        if repository not in self.manifests:
            raise web.HTTPNotFound()
        if kind == "tags":
            return web.json_response({"tags": list(self.manifests[repository])})
        content = self.manifests[repository].get(reference) if kind == "manifests" else self.blobs.get(reference)
        if content is None:
            raise web.HTTPNotFound()
        return web.Response(body=content, headers={"Docker-Content-Digest": _digest(content)})


@pytest_asyncio.fixture
async def registry():
    fake = FakeRegistry()
    app = web.Application()
    app.router.add_get("/token", fake.handle)
    app.router.add_get(r"/v2/{repository:.+}/{kind:tags|manifests|blobs}/{reference:.+}", fake.handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    fake.host = f"127.0.0.1:{runner.addresses[0][1]}"
    yield fake
    await runner.cleanup()


async def import_repo(context: HttpContext, reference: str, channels: list[str] | None = None) -> dict:
    return (await execute(IMPORT, context, {"input": {"reference": reference, "channels": channels}}))["importRepo"]


def _versions(repo: dict) -> list[tuple[str, str | None]]:
    return sorted((flavour["release"]["version"], flavour["release"]["channel"]) for flavour in repo["flavours"])


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_importing_a_repository_writes_its_releases(authenticated_context: HttpContext, registry: FakeRegistry):
    registry.release("org/ome", "1.0.0", "1.0.0")
    registry.release("org/ome", "1.1.0", "1.1.0")

    repo = await import_repo(authenticated_context, registry.reference("org/ome"))

    assert repo["reference"] == registry.reference("org/ome")
    assert _versions(repo) == [("1.0.0", None), ("1.1.0", None)]
    for flavour in repo["flavours"]:
        # The catalogue names the image by the digest the descriptor named, never by a tag.
        assert flavour["image"]["imageString"].startswith(f"{registry.reference('org/ome')}@sha256:")
        assert flavour["release"]["digestPinned"] is True
        assert flavour["release"]["revision"] == "3f2a9c1"
        assert flavour["release"]["app"]["identifier"] == "ome"
        assert flavour["source"]["reference"] == registry.reference("org/ome")

    # The inspection travelled with the release: its actions are in the catalogue.
    assert await models.Definition.objects.filter(flavours__repo_id=repo["id"]).aexists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_release_is_read_once(authenticated_context: HttpContext, registry: FakeRegistry):
    """Releases never change, so the next scan asks for the tag list and for nothing it has seen."""
    registry.release("org/ome", "1.0.0", "1.0.0")
    await import_repo(authenticated_context, registry.reference("org/ome"))

    registry.requests.clear()
    registry.release("org/ome", "1.1.0", "1.1.0")
    repo = await import_repo(authenticated_context, registry.reference("org/ome"))

    assert _versions(repo) == [("1.0.0", None), ("1.1.0", None)]
    # The tag it had read is not asked for again; the new release and its image are.
    assert sorted(registry.fetched("manifests")) == ["/v2/org/ome/manifests/1.1.0", "/v2/org/ome/manifests/1.1.0-vanilla"]
    assert len(registry.fetched("blobs")) == 1
    assert await models.OciRepo.objects.acount() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_followed_channel_moves_to_its_next_build(authenticated_context: HttpContext, registry: FakeRegistry):
    registry.release("org/ome", "1.0.0", "1.0.0")
    registry.release("org/ome", "main", "1.0.0-dev.aaaaaaa", channel="main")
    reference = registry.reference("org/ome")

    repo = await import_repo(authenticated_context, reference, channels=["main"])
    assert _versions(repo) == [("1.0.0", None), ("1.0.0-dev.aaaaaaa", "main")]

    registry.release("org/ome", "main", "1.0.0-dev.bbbbbbb", channel="main")
    repo = await import_repo(authenticated_context, reference)

    # The channel has one release at a time, and the release proper is untouched.
    assert repo["channels"] == ["main"]
    assert _versions(repo) == [("1.0.0", None), ("1.0.0-dev.bbbbbbb", "main")]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_superseded_channel_build_stays_while_it_is_deployed(authenticated_context: HttpContext, registry: FakeRegistry):
    registry.release("org/ome", "main", "1.0.0-dev.aaaaaaa", channel="main")
    reference = registry.reference("org/ome")
    repo = await import_repo(authenticated_context, reference, channels=["main"])

    organization = authenticated_context.request.organization
    backend = await models.Backend.objects.acreate(organization=organization, user=authenticated_context.request.user, client=authenticated_context.request.client, kind="docker", name="b")
    flavour = await models.Flavour.objects.aget(repo_id=repo["id"])
    await models.Deployment.objects.acreate(flavour=flavour, backend=backend)

    registry.release("org/ome", "main", "1.0.0-dev.bbbbbbb", channel="main")
    repo = await import_repo(authenticated_context, reference)

    assert _versions(repo) == [("1.0.0-dev.aaaaaaa", "main"), ("1.0.0-dev.bbbbbbb", "main")]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_channel_nobody_follows_is_not_taken(authenticated_context: HttpContext, registry: FakeRegistry):
    registry.release("org/ome", "1.0.0", "1.0.0")
    registry.release("org/ome", "main", "1.0.0-dev.aaaaaaa", channel="main")

    repo = await import_repo(authenticated_context, registry.reference("org/ome"))

    assert _versions(repo) == [("1.0.0", None)]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_second_repository_cannot_publish_an_app_the_first_one_holds(authenticated_context: HttpContext, registry: FakeRegistry):
    """Importing is trust in one registry namespace; an identifier is not up for grabs after that."""
    registry.release("org/ome", "1.0.0", "1.0.0")
    registry.release("mallory/ome", "9.9.9", "9.9.9")
    await import_repo(authenticated_context, registry.reference("org/ome"))

    hijack = await import_repo(authenticated_context, registry.reference("mallory/ome"))

    assert hijack["flavours"] == []
    assert [release.version async for release in models.Release.objects.filter(app__identifier="ome")] == ["1.0.0"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_release_naming_an_image_elsewhere_is_not_taken(authenticated_context: HttpContext, registry: FakeRegistry):
    registry.release("org/ome", "1.0.0", "1.0.0", image="docker.io/somebody/else@sha256:" + "a" * 64)

    repo = await import_repo(authenticated_context, registry.reference("org/ome"))

    assert repo["flavours"] == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_descriptor_under_another_versions_tag_is_not_taken(authenticated_context: HttpContext, registry: FakeRegistry):
    registry.release("org/ome", "1.0.0", "2.0.0")

    repo = await import_repo(authenticated_context, registry.reference("org/ome"))

    assert repo["flavours"] == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_repository_that_cannot_be_read_is_not_imported(authenticated_context: HttpContext, registry: FakeRegistry):
    result = await execute_raw(IMPORT, authenticated_context, {"input": {"reference": registry.reference("org/missing")}})

    assert result.errors and "has to be public" in result.errors[0].message
    assert await models.OciRepo.objects.acount() == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_reference_with_a_tag_is_refused(authenticated_context: HttpContext, registry: FakeRegistry):
    result = await execute_raw(IMPORT, authenticated_context, {"input": {"reference": registry.reference("org/ome") + ":1.0.0"}})

    assert result.errors and "without a tag" in result.errors[0].message


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_the_hook_action_reads_every_imported_repository_again(authenticated_context: HttpContext, registry: FakeRegistry):
    """What a schedule runs: one pass, new releases written, an unreadable repository counted."""
    registry.release("org/ome", "1.0.0", "1.0.0")
    registry.release("org/other", "1.0.0", "1.0.0", identifier="other")
    await import_repo(authenticated_context, registry.reference("org/ome"))
    await import_repo(authenticated_context, registry.reference("org/other"))

    registry.release("org/ome", "1.1.0", "1.1.0")
    del registry.manifests["org/other"]

    assert await sync_to_async(rescan_sources)("static_org") == {"releases": 1, "unreadable": 1}
    assert await sync_to_async(rescan_sources)("another_org") == {"releases": 0, "unreadable": 0}
    assert await models.Release.objects.filter(app__identifier="ome").acount() == 2


def test_the_descriptor_arkitekt_spec_writes_is_read_here():
    """The format is arkitekt-spec's; this is its golden file, copied. A drift between the two fails here."""
    from bridge.repo.models import ReleaseDescriptorModel

    with open(build_relative_dir("deployments/release.json"), "rb") as f:
        descriptor = ReleaseDescriptorModel.model_validate_json(f.read())

    (flavour,) = descriptor.flavours
    assert (descriptor.manifest.identifier, descriptor.revision) == ("starmist", "3f2a9c1d")
    assert [selector.kind for selector in flavour.selectors] == ["cuda"]
    app_image = flavour.to_app_image(descriptor.manifest)
    assert app_image.image.image_string == flavour.image
    assert app_image.inspection.implementations[0].definition.name == "Segment Fluorescent Nuclei"
