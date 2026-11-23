"""Catalogs: curated lists of repositories an organization reads, e.g. arkitekt.live's.

A catalog is one file at a URL, JSON or YAML (``docs/catalogs.md``), and an organization's:
the ones the hub's config names (``ensure_catalogs``, added to every organization the first
time it lists its catalogs) and the ones it added itself (``createCatalog``). Reading it writes
its entries: matched by key, created, changed or deleted row by row, so each change is
signalled to the organization. A file that cannot be read, or that does not validate, leaves
the entries of the last good read and records why on the catalog.

Nothing here runs on its own. A catalog is read when its organization lists its catalogs and it
was last tried longer ago than ``CATALOG_TTL`` seconds, or when ``refreshCatalog`` asks for it.

Listing is not trusting: an entry is found here, and the organization still imports it, and a
release of it is still approved, before anything of it runs.
"""

import asyncio
import datetime
import json
import logging
import re
from typing import Literal

import aiohttp
import yaml
from asgiref.sync import sync_to_async
from authentikate.models import Organization, User
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from bridge import models
from bridge.enums import CatalogEntryKind as EntryKind
from bridge.repo import oci
from bridge.repo.layout import parse_github_identifier

logger = logging.getLogger(__name__)

#: Far more than any curated list; a bigger file is refused rather than read into memory.
MAX_BYTES = 2 * 1024 * 1024
_TIMEOUT = aiohttp.ClientTimeout(total=10)
_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class CatalogError(Exception):
    """A catalog file could not be read, or is not a catalog."""


def _http_url(value: str | None) -> str | None:
    if value is not None and not value.startswith(("https://", "http://")):
        raise ValueError(f"'{value}' is not an http(s) URL")
    return value


class EntrySpec(BaseModel):
    """One entry of a catalog file. Keys this version does not know are ignored."""

    model_config = ConfigDict(extra="ignore")

    key: str
    kind: EntryKind
    reference: str
    channels: list[str] = Field(default_factory=list)
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    logo: str | None = None
    homepage: str | None = None
    maintainer: str | None = None

    @field_validator("key")
    @classmethod
    def _key(cls, value: str) -> str:
        if not _KEY.match(value) or len(value) > 200:
            raise ValueError(
                f"'{value}' is not a key: lowercase letters, digits, '.', '_' and '-'"
            )
        return value

    @field_validator("logo", "homepage")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        return _http_url(value)

    @model_validator(mode="after")
    def _canonical(self) -> "EntrySpec":
        """Write the reference the one way kabinet stores it, so an import finds it again."""
        if self.kind is EntryKind.OCI:
            registry, repository = oci.parse_reference(self.reference)
            self.reference = f"{registry}/{repository}"
        else:
            if self.channels:
                raise ValueError(
                    f"'{self.key}': only an oci entry follows channels; a github entry is its branch"
                )
            user, repo, branch = parse_github_identifier(self.reference)
            self.reference = f"{user}/{repo}:{branch}"
        return self


class CatalogSpec(BaseModel):
    """A catalog file."""

    model_config = ConfigDict(extra="ignore")

    spec_version: Literal[1]
    name: str
    description: str = ""
    entries: list[EntrySpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_keys(self) -> "CatalogSpec":
        seen: set[str] = set()
        for entry in self.entries:
            if entry.key in seen:
                raise ValueError(f"the key '{entry.key}' is listed twice")
            seen.add(entry.key)
        return self


def parse(content: bytes) -> CatalogSpec:
    """The catalog ``content`` holds: JSON, or else YAML.

    JSON first: YAML reads most JSON, but not JSON indented with tabs.
    """
    try:
        data = json.loads(content)
    except ValueError:
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise CatalogError(f"not JSON or YAML: {e}") from e
    if not isinstance(data, dict):
        raise CatalogError("not a catalog: the file is not a mapping")
    try:
        return CatalogSpec.model_validate(data)
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'file'}: {error['msg']}"
            for error in e.errors()
        )
        raise CatalogError(f"not a catalog: {problems}") from e


async def _fetch(
    session: aiohttp.ClientSession, url: str, etag: str
) -> tuple[bytes | None, str]:
    """The file's bytes and ETag; ``None`` when it is unchanged since ``etag``."""
    headers = {"Accept": "application/json, application/yaml;q=0.9, */*;q=0.5"}
    if etag:
        headers["If-None-Match"] = etag
    try:
        async with session.get(url, headers=headers, timeout=_TIMEOUT) as response:
            if response.status == 304:
                return None, etag
            if response.status != 200:
                raise CatalogError(f"{url} answered {response.status}")
            body = await response.content.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise CatalogError(f"{url} is larger than {MAX_BYTES} bytes")
            return body, response.headers.get("ETag", "")
    except (aiohttp.ClientError, TimeoutError) as e:
        raise CatalogError(f"{url} could not be read: {e or type(e).__name__}") from e


_ENTRY_FIELDS = (
    "kind",
    "reference",
    "channels",
    "name",
    "description",
    "tags",
    "logo_url",
    "homepage",
    "maintainer",
)


def _entry_values(entry: EntrySpec) -> dict[str, object]:
    return {
        "kind": entry.kind.value,
        "reference": entry.reference,
        "channels": entry.channels,
        "name": entry.name,
        "description": entry.description,
        "tags": entry.tags,
        "logo_url": entry.logo,
        "homepage": entry.homepage,
        "maintainer": entry.maintainer,
    }


def _write(catalog_id: int, spec: CatalogSpec | None, etag: str) -> None:
    """Record a good read: ``spec`` is the file, ``None`` when it was unchanged.

    Row by row, so each entry that is new, changed or gone is signalled to the catalog's
    organization, and nothing else is. The catalog row is locked first: two writers of the
    same catalog (a stale read and a ``refreshCatalog``) take turns.
    """
    now = timezone.now()
    with transaction.atomic():
        catalog = models.Catalog.objects.select_for_update().get(id=catalog_id)
        if spec is not None:
            stored = {entry.key: entry for entry in catalog.entries.all()}
            for entry in spec.entries:
                values = _entry_values(entry)
                existing = stored.pop(entry.key, None)
                if existing is None:
                    models.CatalogEntry.objects.create(
                        catalog=catalog, key=entry.key, **values
                    )
                elif any(getattr(existing, f) != v for f, v in values.items()):
                    for field, value in values.items():
                        setattr(existing, field, value)
                    existing.save(update_fields=list(_ENTRY_FIELDS))
            for gone in stored.values():
                gone.delete()
            catalog.name, catalog.description = spec.name, spec.description
        catalog.etag, catalog.error = etag, None
        catalog.checked_at = catalog.fetched_at = now
        catalog.save(
            update_fields=[
                "name",
                "description",
                "etag",
                "error",
                "checked_at",
                "fetched_at",
            ]
        )


def _fail(catalog_id: int, error: str) -> None:
    models.Catalog.objects.filter(id=catalog_id).update(
        checked_at=timezone.now(), error=error
    )


async def _read(session: aiohttp.ClientSession, catalog: models.Catalog) -> None:
    try:
        body, etag = await _fetch(session, catalog.url, catalog.etag)
        spec = parse(body) if body is not None else None
    except CatalogError as e:
        logger.warning("Catalog %s not read: %s", catalog.url, e)
        await sync_to_async(_fail)(catalog.id, str(e))
        return
    await sync_to_async(_write)(catalog.id, spec, etag)


async def refresh(catalog: models.Catalog) -> models.Catalog:
    """Read ``catalog`` now, whenever it was last read; the row as the read left it."""
    async with aiohttp.ClientSession() as session:
        await _read(session, catalog)
    return await models.Catalog.objects.aget(id=catalog.id)


async def add(
    url: str, organization: Organization, creator: User | None
) -> models.Catalog:
    """Add the catalog at ``url`` to ``organization`` and read it, or read it again.

    Read before it is stored: a URL that is not a readable catalog is not added.
    """
    catalog = await models.Catalog.objects.filter(
        organization=organization, url=url
    ).afirst()
    if catalog is not None:
        return await refresh(catalog)
    async with aiohttp.ClientSession() as session:
        body, etag = await _fetch(session, url, "")
    if body is None:  # nothing was sent to match, so a 304 is the server's mistake
        raise CatalogError(f"{url} answered 304 to a first read")
    spec = parse(body)
    catalog, _ = await models.Catalog.objects.aget_or_create(
        organization=organization, url=url, defaults={"creator": creator}
    )
    await sync_to_async(_write)(catalog.id, spec, etag)
    return await models.Catalog.objects.aget(id=catalog.id)


def _ensure(organization: Organization) -> None:
    """Make ``organization``'s config catalogs exactly the ones ``ENSURE_CATALOGS`` names.

    A named catalog it lacks is added (unread); one it added itself becomes the config's; a
    config catalog no longer named is deleted. Its own catalogs stay as they are.
    """
    urls: list[str] = list(dict.fromkeys(settings.ENSURE_CATALOGS))
    for url in urls:
        catalog, created = models.Catalog.objects.get_or_create(
            organization=organization, url=url, defaults={"ensured": True}
        )
        if not created and not catalog.ensured:
            catalog.ensured = True
            catalog.save(update_fields=["ensured"])
    for gone in models.Catalog.objects.filter(
        organization=organization, ensured=True
    ).exclude(url__in=urls):
        gone.delete()


async def ensure(organization: Organization) -> None:
    """``organization``'s config catalogs as the config names them now (``_ensure``)."""
    await sync_to_async(_ensure)(organization)


def _claim(catalog: models.Catalog, cutoff: datetime.datetime) -> bool:
    """Take the read of a stale catalog, unless another request (or replica) just did."""
    now = timezone.now()
    stale = Q(checked_at__isnull=True) | Q(checked_at__lt=cutoff)
    return bool(
        models.Catalog.objects.filter(stale, id=catalog.id).update(checked_at=now)
    )


async def refresh_stale(organization: Organization) -> None:
    """Read every catalog of ``organization`` last tried longer ago than ``CATALOG_TTL``
    seconds, all at once."""
    cutoff = timezone.now() - datetime.timedelta(seconds=settings.CATALOG_TTL)
    stale = [
        catalog
        async for catalog in models.Catalog.objects.filter(
            Q(checked_at__isnull=True) | Q(checked_at__lt=cutoff),
            organization=organization,
        )
    ]
    claimed = [
        catalog for catalog in stale if await sync_to_async(_claim)(catalog, cutoff)
    ]
    if not claimed:
        return
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*(_read(session, catalog) for catalog in claimed))
