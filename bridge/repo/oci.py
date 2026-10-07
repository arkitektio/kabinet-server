"""Reading an app's releases out of an OCI registry.

A repository that carries an app holds two kinds of tags: images, and release descriptors
(small JSON documents naming the images of one release by digest; the format is
arkitekt-spec's ``release``). A scan lists the tags, reads the ones it has not read yet,
and writes every release it finds. Releases never change, so a tag is read once; a
followed channel tag is read again whenever it points somewhere new.

Everything is read anonymously, over the distribution API every registry speaks. A private
repository therefore looks like a missing one, and is reported as such.
"""

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from asgiref.sync import sync_to_async
from django.utils import timezone
from pydantic import ValidationError
from yarl import URL

from bridge import models

from .db import apply_release
from .errors import DBError
from .models import ReleaseDescriptorModel

logger = logging.getLogger(__name__)

#: The media type of a release descriptor: a manifest whose config has it is a release.
RELEASE_MEDIA_TYPE = "application/vnd.arkitekt.release.v1+json"

_ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
    ]
)

DEFAULT_REGISTRY = "docker.io"
_DOCKER_HUB_API = "registry-1.docker.io"

#: A descriptor is a few kilobytes per action. Anything near this is not one.
MAX_DESCRIPTOR_BYTES = 16 * 1024 * 1024
#: How many tags of one repository a scan will look at.
MAX_TAGS = 5000
_CONCURRENCY = 8
_TIMEOUT = aiohttp.ClientTimeout(total=30)


class RegistryError(Exception):
    """A registry could not be read."""


def parse_reference(reference: str) -> tuple[str, str]:
    """Split a repository reference into registry host and repository path, as docker does."""
    reference = reference.strip().removeprefix("oci://").removeprefix("https://")
    if not reference or "@" in reference or ":" in reference.rsplit("/", 1)[-1]:
        raise ValueError(f"'{reference}' is not a repository: name the repository alone, without a tag or a digest.")
    head, _, rest = reference.partition("/")
    if rest and ("." in head or ":" in head or head == "localhost"):
        registry, repository = head, rest
    else:
        registry, repository = DEFAULT_REGISTRY, reference
        if "/" not in repository:
            repository = f"library/{repository}"
    if repository != repository.lower() or " " in repository:
        raise ValueError(f"'{repository}' is not a valid repository path (lowercase, no spaces).")
    return registry, repository


@dataclass
class Registry:
    """One repository on one registry, read anonymously."""

    registry: str
    repository: str
    session: aiohttp.ClientSession
    _authorization: str | None = field(default=None, repr=False)

    def _url(self, path: str) -> str:
        host = _DOCKER_HUB_API if self.registry == DEFAULT_REGISTRY else self.registry
        local = host.split(":")[0] in ("localhost", "127.0.0.1")
        return f"{'http' if local else 'https'}://{host}/v2/{self.repository}/{path}"

    async def _get(self, url: str, accept: str | None = None) -> tuple[int, Any, bytes]:
        """GET a url, answering the registry's token challenge once. Returns (status, headers, body)."""
        for _ in range(2):
            headers = {"Accept": accept} if accept else {}
            if self._authorization:
                headers["Authorization"] = self._authorization
            try:
                async with self.session.get(url, headers=headers, timeout=_TIMEOUT) as response:
                    if response.status == 401 and await self._authorize(response.headers.get("WWW-Authenticate", "")):
                        continue
                    body = await response.content.read(MAX_DESCRIPTOR_BYTES + 1)
                    return response.status, response.headers, body
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                raise RegistryError(f"Could not reach {self.registry}: {e}") from e
        raise RegistryError(f"{self.registry} did not accept the token it issued.")

    async def _authorize(self, challenge: str) -> bool:
        scheme, _, rest = challenge.partition(" ")
        parameters = dict(re.findall(r'(\w+)="([^"]*)"', rest))
        if scheme.lower() != "bearer" or "realm" not in parameters or self._authorization:
            return False
        query = {key: parameters[key] for key in ("service", "scope") if key in parameters}
        try:
            async with self.session.get(parameters["realm"], params=query, timeout=_TIMEOUT) as response:
                if response.status != 200:
                    return False
                granted = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            return False
        token = granted.get("token") or granted.get("access_token")
        if not token:
            return False
        self._authorization = f"Bearer {token}"
        return True

    def _missing(self) -> RegistryError:
        return RegistryError(
            f"{self.registry}/{self.repository} could not be read. Either it does not exist, or it is private: "
            "kabinet reads registries anonymously, so the repository (on GitHub: the package) has to be public."
        )

    async def tags(self) -> list[str]:
        """Every tag of the repository, following the registry's pagination."""
        tags: list[str] = []
        url: str | None = self._url("tags/list?n=1000")
        while url and len(tags) < MAX_TAGS:
            status, headers, body = await self._get(url)
            if status in (401, 403, 404):
                raise self._missing()
            if status != 200:
                raise RegistryError(f"{self.registry} answered {status} when listing the tags of {self.repository}.")
            tags.extend(json.loads(body).get("tags") or [])
            following = re.search(r'<([^>]+)>;\s*rel="next"', headers.get("Link", ""))
            url = str(URL(url).join(URL(following.group(1)))) if following else None
        return tags[:MAX_TAGS]

    async def manifest(self, reference: str) -> tuple[str, dict[str, Any]] | None:
        """The digest and content of the manifest a tag names, or None if there is none."""
        status, headers, body = await self._get(self._url(f"manifests/{reference}"), accept=_ACCEPT)
        if status == 404:
            return None
        if status != 200:
            raise RegistryError(f"{self.registry} answered {status} for {self.repository}:{reference}.")
        digest = headers.get("Docker-Content-Digest") or "sha256:" + hashlib.sha256(body).hexdigest()
        try:
            content = json.loads(body)
        except ValueError:
            content = {}
        return digest, content if isinstance(content, dict) else {}

    async def descriptor(self, manifest: dict[str, Any]) -> ReleaseDescriptorModel | None:
        """The release a manifest carries, or None when the manifest is an image."""
        config = manifest.get("config")
        if not isinstance(config, dict) or config.get("mediaType") != RELEASE_MEDIA_TYPE:
            return None
        digest, size = config.get("digest"), config.get("size")
        if not isinstance(digest, str) or not isinstance(size, int) or size > MAX_DESCRIPTOR_BYTES:
            raise RegistryError(f"A release in {self.repository} names a descriptor of {size} bytes, which is not read.")
        status, _, body = await self._get(self._url(f"blobs/{digest}"))
        if status != 200:
            raise RegistryError(f"{self.registry} answered {status} for the descriptor {digest}.")
        if "sha256:" + hashlib.sha256(body).hexdigest() != digest:
            raise RegistryError(f"{self.registry} returned other bytes than {digest} names.")
        return ReleaseDescriptorModel.model_validate_json(body)


@dataclass
class ScanReport:
    """What one scan of a repository found."""

    releases: list[models.Release] = field(default_factory=list)
    problems: dict[str, str] = field(default_factory=dict)


def _belongs(descriptor: ReleaseDescriptorModel, tag: str, repo: models.OciRepo) -> str | None:
    """Why a descriptor found under a tag is not taken, or None when it is."""
    if descriptor.channel is None and tag != descriptor.manifest.version:
        return f"it describes version {descriptor.manifest.version}, which is not the tag it sits under"
    if descriptor.channel is not None and tag not in repo.channels:
        return "it is a channel build, and this channel is not followed"
    for flavour in descriptor.flavours:
        if not flavour.image.startswith(f"{repo.reference}@"):
            return f"its flavour {flavour.name} names an image outside this repository ({flavour.image})"
    return None


async def scan(repo: models.OciRepo, session: aiohttp.ClientSession | None = None) -> ScanReport:
    """Read every tag of a repository that was not read yet, and write the releases found.

    One bad tag does not hide the others: what could not be taken is reported per tag, and
    remembered with the digest it had, so it is looked at again only once it changes.
    """
    if session is None:
        async with aiohttp.ClientSession() as own:
            return await scan(repo, own)

    registry = Registry(repo.registry, repo.repository, session)
    organization = await models.Organization.objects.aget(pk=repo.organization_id)
    report = ScanReport()
    seen: dict[str, str] = dict(repo.seen or {})
    limit = asyncio.Semaphore(_CONCURRENCY)

    found: dict[str, tuple[str, ReleaseDescriptorModel | None]] = {}

    async def read(tag: str) -> None:
        async with limit:
            digest = None
            try:
                manifest = await registry.manifest(tag)
                if manifest is None or seen.get(tag) == manifest[0]:
                    return
                digest = manifest[0]
                found[tag] = digest, await registry.descriptor(manifest[1])
            except ValidationError as e:
                report.problems[tag] = str(e)
                if digest:
                    seen[tag] = digest
            except RegistryError as e:
                # Not remembered: the registry may answer the next scan.
                report.problems[tag] = str(e)

    tags = await registry.tags()
    await asyncio.gather(*(read(tag) for tag in tags if tag in repo.channels or tag not in seen))

    # Written one after the other: two releases of one app must not race for its row.
    for tag in sorted(found):
        digest, descriptor = found[tag]
        seen[tag] = digest
        if descriptor is None:
            continue
        refusal = _belongs(descriptor, tag, repo)
        if refusal:
            report.problems[tag] = refusal
            continue
        try:
            report.releases.append(await sync_to_async(apply_release)(descriptor, repo, organization))
        except DBError as e:
            report.problems[tag] = str(e)

    for tag, problem in report.problems.items():
        logger.warning("Did not take %s:%s: %s", repo, tag, problem)

    repo.seen = seen
    repo.scanned_at = timezone.now()
    await repo.asave(update_fields=["seen", "scanned_at"])
    return report
