"""Fetching a repository's ``deployments.yaml`` and saying what is wrong when it fails.

Every failure in here used to collapse into one of two sentences -- "This does not look
like an Arkitekt repository" for any non-200, and "did not contain a YAML mapping" for
anything the YAML parser did not return a dict for -- or, for a file that parsed but did
not validate, into a raw pydantic ``ValidationError`` traceback. None of those tell the
person tracking a repo which of the half-dozen quite different things went wrong, and the
most likely one right now is a repo still publishing the pre-rename ``.arkitekt_next``
folder.

A 404 is therefore diagnosed before it is reported: the sibling paths that would explain
it are probed on the same host the fetch already uses (``raw.githubusercontent.com`` --
never the GitHub API, whose 60-requests-per-hour anonymous limit would turn a `rescanRepos`
over a handful of broken repos into a wall of 403s that say nothing about the repos). The
diagnosis is best-effort: if probing itself fails, the plain "HTTP 404 at <url>" stands.
"""

import logging
from typing import NamedTuple

import aiohttp
import yaml
from pydantic import ValidationError

from .errors import RepoError
from .layout import CONFIG_DIR, DEPLOYMENTS_PATH, LEGACY_CONFIG_DIRS, MANIFEST_PATH, ROOT_MARKER_PATHS, raw_url
from .models import KabinetConfigFile

logger = logging.getLogger(__name__)

#: A manifest fetch is a request to a third party made inside a GraphQL request. Without
#: a bound, one unreachable host holds a worker until the client gives up -- and
#: `rescanRepos` makes one of these per repo.
FETCH_TIMEOUT_SECONDS = 30

#: The diagnosis runs after a fetch has already failed, so it gets a tighter budget: it
#: exists to improve an error message, not to double how long the caller waits for one.
DIAGNOSIS_TIMEOUT_SECONDS = 5


class InspectionError(RepoError, ValueError):
    """A repository could not be read as an Arkitekt repository.

    ``ValueError`` as well as ``RepoError`` because that is what the resolvers raised
    before, and strawberry turns it into a GraphQL error for the client either way.
    """


class RepoCoordinates(NamedTuple):
    """What it takes to address a file in a GitHub repository.

    Passed alongside the URL rather than parsed back out of it, and passed as a tuple
    rather than as a ``GithubRepo``: ``createGithubRepo`` inspects the repository before
    it creates the row, so at that call site no model instance exists yet.
    """

    user: str
    repo: str
    branch: str

    def __str__(self) -> str:
        return f"{self.user}/{self.repo}:{self.branch}"

    def url_for(self, path: str) -> str:
        return raw_url(self.user, self.repo, self.branch, path)


async def _aprobe(session: aiohttp.ClientSession, url: str) -> bool:
    """Is there a file at ``url``? ``False`` also when the question could not be asked."""
    try:
        async with session.head(url) as response:
            return response.status == 200
    except (aiohttp.ClientError, TimeoutError):
        return False


async def _adiagnose_missing(coordinates: RepoCoordinates) -> str:
    """Explain a 404 on ``deployments.yaml`` by looking at what *is* published."""
    timeout = aiohttp.ClientTimeout(total=DIAGNOSIS_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(headers={"Cache-Control": "no-cache"}, timeout=timeout) as session:
        for legacy in LEGACY_CONFIG_DIRS:
            if await _aprobe(session, coordinates.url_for(f"{legacy}/deployments.yaml")):
                return (
                    f"{coordinates} still publishes its deployments as `{legacy}/deployments.yaml`. "
                    f"Kabinet reads `{DEPLOYMENTS_PATH}` now -- rename the folder to `{CONFIG_DIR}/` and push."
                )

        if await _aprobe(session, coordinates.url_for(MANIFEST_PATH)):
            return (
                f"{coordinates} has a `{CONFIG_DIR}/` folder with a manifest, but no `{DEPLOYMENTS_PATH}`. "
                "That file is written when app images are built and published -- build and push one "
                "(`arkitekt build` then `arkitekt publish`) before tracking the repo."
            )

        for marker in ROOT_MARKER_PATHS:
            if await _aprobe(session, coordinates.url_for(marker)):
                return (
                    f"{coordinates} exists and is readable, but has no `{CONFIG_DIR}/` folder on this branch. "
                    "Only repositories that publish Arkitekt app images can be tracked; check that you meant "
                    f"this branch (`{coordinates.branch}`)."
                )

        return (
            f"Nothing could be read from {coordinates} at all -- not even a README. "
            "Check the owner, repository name and branch, and that the repository is public "
            "(kabinet fetches anonymously, so a private repository looks exactly like a missing one)."
        )


async def _adescribe_failed_fetch(coordinates: RepoCoordinates, url: str, status: int) -> str:
    """Turn a non-200 on the deployments fetch into something actionable."""
    if status == 404:
        try:
            return await _adiagnose_missing(coordinates)
        except Exception:
            # The diagnosis is a nicety. Losing it must not cost the caller the error the
            # fetch actually produced.
            logger.warning("Could not diagnose the missing config of %s", coordinates, exc_info=True)
            return f"{url} does not exist (HTTP 404)."

    if status in (401, 403):
        return (
            f"GitHub refused to serve {url} (HTTP {status}). Kabinet fetches anonymously, so this is "
            "usually a private repository, or GitHub rate-limiting this server."
        )
    if status >= 500:
        return f"GitHub could not serve {url} right now (HTTP {status}). This is an outage on their side -- retry later."
    return f"Fetching {url} returned an unexpected HTTP {status}."


def _describe_validation_error(error: ValidationError, url: str) -> str:
    """List what is wrong with a parsed-but-invalid config, field by field."""
    problems = []
    for detail in error.errors():
        location = ".".join(str(part) for part in detail["loc"]) or "<root>"
        problems.append(f"  - {location}: {detail['msg']}")
    return f"{url} is not a valid kabinet deployments file. {error.error_count()} problem(s):\n" + "\n".join(problems)


async def aget_kabinet_config(kabinet_url: str, coordinates: RepoCoordinates) -> KabinetConfigFile:
    """Fetch and parse a repository's published ``deployments.yaml``.

    The status check was an ``assert``, which ``python -O`` strips -- leaving a 404 body
    to be handed to the YAML parser.
    """
    timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT_SECONDS)
    try:
        async with aiohttp.ClientSession(headers={"Cache-Control": "no-cache"}, timeout=timeout) as session:
            async with session.get(kabinet_url) as response:
                status = response.status
                body = await response.text() if status == 200 else ""
    except TimeoutError as e:
        # aiohttp raises the builtin TimeoutError, not a ClientError, when the total
        # budget runs out.
        raise InspectionError(f"Fetching {kabinet_url} took longer than {FETCH_TIMEOUT_SECONDS}s and was given up on.") from e
    except aiohttp.ClientError as e:
        raise InspectionError(f"Could not reach {kabinet_url}: {e}") from e

    if status != 200:
        # Diagnosed out here rather than inside the `session.get` context: the probes are
        # up to five more round-trips, and there is no reason to hold the failed
        # response's connection (and its session) open across all of them.
        raise InspectionError(await _adescribe_failed_fetch(coordinates, kabinet_url, status))

    if not body.strip():
        raise InspectionError(f"{kabinet_url} exists but is empty, so it describes no app images.")

    try:
        parsed = yaml.safe_load(body)
    except yaml.YAMLError as e:
        where = ""
        mark = getattr(e, "problem_mark", None)
        if mark is not None:
            where = f" at line {mark.line + 1}, column {mark.column + 1}"
        raise InspectionError(f"{kabinet_url} is not valid YAML{where}: {getattr(e, 'problem', None) or e}") from e

    if not isinstance(parsed, dict):
        raise InspectionError(f"{kabinet_url} contains a {type(parsed).__name__}, not a mapping of keys, so it is not a deployments file.")

    try:
        config = KabinetConfigFile(**parsed)
    except ValidationError as e:
        raise InspectionError(_describe_validation_error(e, kabinet_url)) from e

    if not config.app_images:
        # `app_images` defaults to [], so a mapping without the key validates happily and
        # the scan then reports success having written nothing at all.
        raise InspectionError(
            f"{kabinet_url} is a valid deployments file but lists no app images "
            "(`app_images` is missing or empty), so there is nothing to track. "
            "Publish an app image to the repository first."
        )

    return config
