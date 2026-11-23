"""Catalogs: curated lists of repositories an organization reads, and importing what they list.

Every read goes to a real HTTP server standing in for the host of a catalog file (arkitekt.live
in a hub), with the ETag handling a static host has; importing an entry goes to the same fake
registry and fake raw file host the repository tests use.
"""

import hashlib
import json
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
import yaml
from aiohttp import web
from asgiref.sync import sync_to_async
from kante.context import HttpContext
from pytest_django.fixtures import SettingsWrapper

from bridge import models
from bridge.repo import layout
from tests.test_oci_repo import FakeRegistry, registry  # noqa: F401 - the fixture
from tests.utils import COORDINATES, ServeRepo, execute, execute_raw

CATALOGS = """
    query {
        catalogs {
            id url ensured name error fetchedAt
            entries { id key kind reference channels name tags logoUrl }
        }
    }
"""

REFRESH = """
    mutation Refresh($input: RefreshCatalogInput!) {
        refreshCatalog(input: $input) { id name error entries { id key name reference } }
    }
"""

CREATE = """
    mutation Create($input: CreateCatalogInput!) {
        createCatalog(input: $input) { id url ensured error entries { key } }
    }
"""

DELETE = """
    mutation Delete($input: DeleteCatalogInput!) { deleteCatalog(input: $input) }
"""

IMPORT_ENTRY = """
    mutation Import($input: ImportCatalogEntryInput!) {
        importCatalogEntry(input: $input) {
            key
            ociRepo { id reference channels }
            githubRepo { id user repo branch }
        }
    }
"""

ENTRY = """
    query Entry($id: ID!) {
        catalogEntry(id: $id) { key ociRepo { id } githubRepo { id } }
    }
"""


def _catalog(*entries: dict, name: str = "Arkitekt") -> dict:
    return {"spec_version": 1, "name": name, "entries": list(entries)}


OME = {
    "key": "ome",
    "kind": "oci",
    "reference": "ghcr.io/arkitektio/ome",
    "name": "OME",
    "description": "Read OME files",
    "tags": ["io", "microscopy"],
    "logo": "https://arkitekt.live/logos/ome.png",
}
RENDERER = {
    "key": "renderer",
    "kind": "github",
    "reference": "https://github.com/jhnnsrs/renderer",
    "name": "Renderer",
}


class CatalogHost:
    """Catalog files by name, served with an ETag the way a static host serves them."""

    def __init__(self) -> None:
        self.files: dict[str, bytes | int] = {}
        #: Every request, with the ``If-None-Match`` it carried.
        self.requests: list[tuple[str, str | None]] = []
        self.base = ""

    def put(self, name: str, content: dict | str | int) -> str:
        if isinstance(content, dict):
            self.files[name] = json.dumps(content).encode()
        elif isinstance(content, str):
            self.files[name] = content.encode()
        else:
            self.files[name] = content
        return self.url(name)

    def url(self, name: str) -> str:
        return f"{self.base}/{name}"

    async def handle(self, request: web.Request) -> web.Response:
        name = request.match_info["name"]
        self.requests.append((name, request.headers.get("If-None-Match")))
        content = self.files.get(name)
        if content is None:
            raise web.HTTPNotFound()
        if isinstance(content, int):
            return web.Response(status=content)
        etag = f'"{hashlib.sha256(content).hexdigest()[:16]}"'
        if request.headers.get("If-None-Match") == etag:
            return web.Response(status=304, headers={"ETag": etag})
        return web.Response(body=content, headers={"ETag": etag})


@pytest_asyncio.fixture
async def host() -> AsyncIterator[CatalogHost]:
    fake = CatalogHost()
    app = web.Application()
    app.router.add_get("/{name}", fake.handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    fake.base = f"http://127.0.0.1:{runner.addresses[0][1]}"
    yield fake
    await runner.cleanup()


async def _add(context: HttpContext, url: str) -> models.Catalog:
    """A catalog of the context's organization, as an organization's own (not the config's)."""
    return await models.Catalog.objects.acreate(
        url=url, organization=context.request.organization
    )


async def _list(context: HttpContext) -> list[dict]:
    return (await execute(CATALOGS, context))["catalogs"]


async def _refresh(context: HttpContext, catalog_id: str) -> dict:
    return (await execute(REFRESH, context, {"input": {"id": catalog_id}}))[
        "refreshCatalog"
    ]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_listing_reads_a_catalog_and_writes_its_entries(
    authenticated_context: HttpContext, host: CatalogHost
) -> None:
    await _add(authenticated_context, host.put("default.json", _catalog(OME, RENDERER)))

    [catalog] = await _list(authenticated_context)

    assert catalog["name"] == "Arkitekt"
    assert catalog["error"] is None
    assert catalog["fetchedAt"] is not None
    assert [
        (e["key"], e["kind"], e["reference"], e["tags"], e["logoUrl"])
        for e in catalog["entries"]
    ] == [
        ("ome", "OCI", "ghcr.io/arkitektio/ome", ["io", "microscopy"], OME["logo"]),
        # A github.com URL is stored as the identifier createGithubRepo would make of it.
        ("renderer", "GITHUB", "jhnnsrs/renderer:main", [], None),
    ]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_catalog_may_be_yaml(
    authenticated_context: HttpContext, host: CatalogHost
) -> None:
    await _add(
        authenticated_context, host.put("default.yaml", yaml.safe_dump(_catalog(OME)))
    )

    [catalog] = await _list(authenticated_context)

    assert [e["key"] for e in catalog["entries"]] == ["ome"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_catalog_may_be_json_indented_with_tabs(
    authenticated_context: HttpContext, host: CatalogHost
) -> None:
    await _add(
        authenticated_context,
        host.put("default.json", json.dumps(_catalog(OME), indent="\t")),
    )

    [catalog] = await _list(authenticated_context)

    assert catalog["error"] is None
    assert [e["key"] for e in catalog["entries"]] == ["ome"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_catalog_read_lately_is_not_read_again(
    authenticated_context: HttpContext, host: CatalogHost
) -> None:
    await _add(authenticated_context, host.put("default.json", _catalog(OME)))

    await _list(authenticated_context)
    await _list(authenticated_context)

    assert len(host.requests) == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_stale_catalog_is_asked_with_its_etag(
    authenticated_context: HttpContext, host: CatalogHost, settings: SettingsWrapper
) -> None:
    settings.CATALOG_TTL = 0
    await _add(authenticated_context, host.put("default.json", _catalog(OME)))

    await _list(authenticated_context)
    [catalog] = await _list(authenticated_context)

    [(_, first), (_, second)] = host.requests
    assert first is None
    assert second is not None  # answered 304: nothing was read, nothing changed
    assert [e["key"] for e in catalog["entries"]] == ["ome"]
    assert catalog["error"] is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_reading_again_updates_entries_by_key_and_drops_the_unlisted(
    authenticated_context: HttpContext, host: CatalogHost
) -> None:
    url = host.put("default.json", _catalog(OME, RENDERER))
    await _add(authenticated_context, url)
    [catalog] = await _list(authenticated_context)
    ome_id = catalog["entries"][0]["id"]

    host.put(
        "default.json",
        _catalog(
            {**OME, "name": "OME tools"}, {**RENDERER, "key": "viewer"}, name="New"
        ),
    )
    refreshed = await _refresh(authenticated_context, catalog["id"])

    assert refreshed["name"] == "New"
    assert sorted((e["key"], e["name"]) for e in refreshed["entries"]) == [
        ("ome", "OME tools"),
        ("viewer", "Renderer"),
    ]
    assert [e["id"] for e in refreshed["entries"] if e["key"] == "ome"] == [ome_id]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("broken", "says"),
    [
        (500, "answered 500"),
        ("entries: [unclosed", "not JSON or YAML"),
        (_catalog(OME, OME), "the key 'ome' is listed twice"),
        (_catalog({**OME, "reference": "ghcr.io/arkitektio/ome:1.0"}), "without a tag"),
        (
            _catalog({**RENDERER, "channels": ["main"]}),
            "only an oci entry follows channels",
        ),
        ({"spec_version": 2, "name": "Future", "entries": []}, "spec_version"),
    ],
)
async def test_a_broken_catalog_keeps_the_entries_of_the_last_good_read(
    authenticated_context: HttpContext,
    host: CatalogHost,
    broken: dict | str | int,
    says: str,
) -> None:
    await _add(authenticated_context, host.put("default.json", _catalog(OME)))
    [catalog] = await _list(authenticated_context)

    host.put("default.json", broken)
    refreshed = await _refresh(authenticated_context, catalog["id"])

    assert says in refreshed["error"]
    assert [e["key"] for e in refreshed["entries"]] == ["ome"]

    host.put("default.json", _catalog(OME))
    assert (await _refresh(authenticated_context, catalog["id"]))["error"] is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_listing_gives_the_organization_the_catalogs_the_config_names(
    authenticated_context: HttpContext, host: CatalogHost, settings: SettingsWrapper
) -> None:
    a, b, own = (
        host.put(name, _catalog(OME)) for name in ("a.json", "b.json", "own.json")
    )
    await _add(authenticated_context, own)

    settings.ENSURE_CATALOGS = [a, b]
    first = {c["url"]: c["ensured"] for c in await _list(authenticated_context)}
    ids = {c["url"]: c["id"] for c in await _list(authenticated_context)}

    # The config no longer names `a` and now names the organization's own catalog.
    settings.ENSURE_CATALOGS = [b, own]
    second = {
        c["url"]: (c["ensured"], c["id"]) for c in await _list(authenticated_context)
    }

    assert first == {a: True, b: True, own: False}
    assert second == {b: (True, ids[b]), own: (True, ids[own])}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_an_organization_adds_and_removes_its_own_catalogs(
    authenticated_context: HttpContext, host: CatalogHost, settings: SettingsWrapper
) -> None:
    settings.ENSURE_CATALOGS = [host.put("default.json", _catalog(OME))]
    [ensured] = await _list(authenticated_context)

    added = (
        await execute(
            CREATE,
            authenticated_context,
            {
                "input": {
                    "url": host.put("lab.yaml", yaml.safe_dump(_catalog(RENDERER)))
                }
            },
        )
    )["createCatalog"]
    assert (added["ensured"], [e["key"] for e in added["entries"]]) == (
        False,
        ["renderer"],
    )

    await execute(DELETE, authenticated_context, {"input": {"id": added["id"]}})
    refused = await execute_raw(
        DELETE, authenticated_context, {"input": {"id": ensured["id"]}}
    )

    assert refused.errors and "config" in refused.errors[0].message
    assert [c["id"] for c in await _list(authenticated_context)] == [ensured["id"]]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("served", "says"),
    [(404, "answered 404"), ("just: text", "not a catalog")],
)
async def test_a_url_that_is_no_catalog_is_not_added(
    authenticated_context: HttpContext,
    host: CatalogHost,
    served: str | int,
    says: str,
) -> None:
    result = await execute_raw(
        CREATE, authenticated_context, {"input": {"url": host.put("x.json", served)}}
    )

    assert result.errors and says in result.errors[0].message
    assert await models.Catalog.objects.acount() == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_another_organization_neither_sees_nor_reads_a_catalog(
    authenticated_context: HttpContext,
    other_org_context: HttpContext,
    host: CatalogHost,
) -> None:
    await _add(authenticated_context, host.put("default.json", _catalog(OME)))
    [catalog] = await _list(authenticated_context)
    entry_id = catalog["entries"][0]["id"]
    requests = len(host.requests)

    assert await _list(other_org_context) == []
    entries = await execute("query { catalogEntries { id } }", other_org_context)
    assert entries["catalogEntries"] == []
    for document, variables in [
        ("query($id: ID!) { catalog(id: $id) { id } }", {"id": catalog["id"]}),
        (ENTRY, {"id": entry_id}),
        (REFRESH, {"input": {"id": catalog["id"]}}),
        (DELETE, {"input": {"id": catalog["id"]}}),
        (IMPORT_ENTRY, {"input": {"id": entry_id}}),
    ]:
        assert (await execute_raw(document, other_org_context, variables)).errors
    # Listing its own catalogs read nothing of another organization's.
    assert len(host.requests) == requests
    assert await models.Catalog.objects.acount() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_importing_an_oci_entry_imports_its_repository(
    authenticated_context: HttpContext,
    host: CatalogHost,
    registry: FakeRegistry,  # noqa: F811 - the fixture
) -> None:
    registry.release("org/ome", "1.0.0", "1.0.0")
    entry = {**OME, "reference": registry.reference("org/ome"), "channels": ["main"]}
    await _add(authenticated_context, host.put("default.json", _catalog(entry)))
    [catalog] = await _list(authenticated_context)
    entry_id = catalog["entries"][0]["id"]

    imported = (
        await execute(IMPORT_ENTRY, authenticated_context, {"input": {"id": entry_id}})
    )["importCatalogEntry"]

    assert imported["ociRepo"]["reference"] == registry.reference("org/ome")
    assert imported["ociRepo"]["channels"] == [
        "main"
    ]  # the catalog's, as none were given
    assert imported["githubRepo"] is None
    assert await models.OciRepo.objects.acount() == 1

    # Importing again reads it again and keeps the channels the organization chose since.
    await execute(
        """mutation($input: ImportRepoInput!) { importRepo(input: $input) { id } }""",
        authenticated_context,
        {"input": {"reference": registry.reference("org/ome"), "channels": []}},
    )
    again = (
        await execute(IMPORT_ENTRY, authenticated_context, {"input": {"id": entry_id}})
    )["importCatalogEntry"]
    assert again["ociRepo"]["channels"] == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_importing_a_github_entry_tracks_the_repository(
    authenticated_context: HttpContext, host: CatalogHost, fake_github: ServeRepo
) -> None:
    await fake_github(
        {
            layout.BLOKS_PATH: yaml.safe_dump(
                {
                    "spec_version": 1,
                    "bloks": [
                        {
                            "key": "hello",
                            "vocab": 2,
                            "name": "Hello",
                            "bsx": '<Blok kind="custom" context="panel"><Card><Text>Hi</Text></Card></Blok>',
                        }
                    ],
                }
            )
        }
    )
    reference = f"{COORDINATES.user}/{COORDINATES.repo}:{COORDINATES.branch}"
    entry = {**RENDERER, "reference": reference}
    await _add(authenticated_context, host.put("default.json", _catalog(entry)))
    [catalog] = await _list(authenticated_context)

    imported = (
        await execute(
            IMPORT_ENTRY,
            authenticated_context,
            {"input": {"id": catalog["entries"][0]["id"]}},
        )
    )["importCatalogEntry"]

    assert imported["ociRepo"] is None
    assert imported["githubRepo"] is not None
    repo = await models.GithubRepo.objects.aget(id=imported["githubRepo"]["id"])
    assert (repo.user, repo.repo, repo.branch) == (
        COORDINATES.user,
        COORDINATES.repo,
        COORDINATES.branch,
    )
    assert await sync_to_async(repo.bloks.count)() == 1
