"""Tracking GitHub repositories and scanning them for app manifests.

The three call sites below used to disagree about what a failed scan means: two caught
``KeyError``, logged it and returned success, and the third caught it, logged it,
``pass``ed and then re-raised. ``parse_config`` raises ``DBError``, never ``KeyError``, so
none of those handlers ever ran -- and a `scanRepo` that failed still answered with a
repo, as though it had worked. They share one contract now: a scan that could not be
applied is an error, except in `rescanRepos`, where one bad repo must not abort the rest.
"""

import asyncio
import logging
import re

import aiohttp
import yaml
from asgiref.sync import sync_to_async
from authentikate.models import Organization, User
from kante.types import Info

from bridge import inputs, models, types
from bridge.repo.db import parse_config
from bridge.repo.models import KabinetConfigFile
from bridge.scoping import aget_for_org, for_org

logger = logging.getLogger(__name__)

#: A manifest fetch is a request to a third party made inside a GraphQL request. Without
#: a bound, one unreachable host holds a worker until the client gives up -- and
#: `rescanRepos` makes one of these per repo.
FETCH_TIMEOUT_SECONDS = 30


async def aget_kabinet_config(kabinet_url: str) -> KabinetConfigFile:
    """Fetch and parse a repository's ``kabinet.yml``.

    The status check was an ``assert``, which ``python -O`` strips -- leaving a 404 body
    to be handed to the YAML parser.
    """
    timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(headers={"Cache-Control": "no-cache"}, timeout=timeout) as session:
        async with session.get(kabinet_url) as response:
            if response.status != 200:
                raise ValueError(f"This does not look like an Arkitekt repository: fetching {kabinet_url} returned HTTP {response.status}.")

            body = await response.text()

    parsed = yaml.safe_load(body)
    if not isinstance(parsed, dict):
        raise ValueError(f"{kabinet_url} did not contain a YAML mapping, so it is not a valid kabinet.yml.")

    return KabinetConfigFile(**parsed)


async def scan_repo(info: Info, input: inputs.ScanRepoInput) -> types.GithubRepo:
    """Scan a tracked GitHub repository for app manifests and update its flavours."""
    parsed = input.to_pydantic()
    repo = await aget_for_org(models.GithubRepo, info, id=parsed.id)

    config = await aget_kabinet_config(repo.kabinet_url)

    await sync_to_async(parse_config)(config, repo, info.context.request.organization)

    return repo


def infer_repo_info(input: inputs.CreateGithubRepoInputModel) -> tuple[str, str, str, str]:
    """Resolve (user, repo, branch, name) from either an identifier or explicit fields.

    Two things used to be wrong here beyond the `assert`s. The identifier branch computed
    a `name` and then returned `input.identifier` in that slot instead -- and it built
    that discarded name from `input.user`/`input.repo`, which are None on exactly the
    path that supplies an identifier. So the two branches returned different meanings for
    the same tuple position. Both now return the same `user/repo:branch` name.

    Validation is explicit rather than `assert`: these check client input, and asserts
    are stripped under `python -O`.
    """
    if input.identifier:
        # A full GitHub URL, with or without a /tree/<branch> suffix.
        match = re.match(r"https:\/\/github\.com\/([^\/]+)\/([^\/]+)(?:\/tree\/([^\/]+))?", input.identifier)
        if match:
            user, repo, branch = match.groups()
            branch = branch or "main"
        elif "/" in input.identifier:
            # The short form: "user/repo" or "user/repo:branch".
            user, repo_with_branch = input.identifier.split("/", 1)
            if ":" in repo_with_branch:
                repo, branch = repo_with_branch.split(":", 1)
            else:
                repo, branch = repo_with_branch, "main"
        else:
            raise ValueError(f"'{input.identifier}' is not a GitHub identifier. Expected a github.com URL, 'user/repo', or 'user/repo:branch'.")
    else:
        if not (input.user and input.repo):
            raise ValueError("Either identifier, or both user and repo, must be provided.")
        user, repo, branch = input.user, input.repo, input.branch or "main"

    return user, repo, branch, f"{user}/{repo}:{branch}"


async def _create_github_repo(
    input: inputs.CreateGithubRepoInputModel,
    organization: Organization,
    creator: User,
) -> models.GithubRepo:
    user, repo, branch, name = infer_repo_info(input)

    dep_url = models.GithubRepo.build_kabinet_url(user, repo, branch)

    config = await aget_kabinet_config(dep_url)

    repo, _ = await models.GithubRepo.objects.aget_or_create(
        user=user,
        branch=branch,
        repo=repo,
        organization=organization,
        defaults=dict(
            name=name,
            creator=creator,
        ),
    )

    await sync_to_async(parse_config)(config, repo, organization)

    return repo


async def create_github_repo(info: Info, input: inputs.CreateGithubRepoInput) -> types.GithubRepo:
    parsed = input.to_pydantic()
    return await _create_github_repo(parsed, info.context.request.organization, info.context.request.user)


async def _rescan_one(repo: models.GithubRepo, organization: Organization) -> None:
    """Rescan a single repo, logging rather than raising when it cannot be scanned."""
    try:
        config = await aget_kabinet_config(repo.kabinet_url)
        await sync_to_async(parse_config)(config, repo, organization)
    except Exception:
        # One unreachable or malformed repo must not take the other N down with it. This
        # is the one place where swallowing a scan failure is the right answer.
        logger.warning("Could not rescan %s", repo, exc_info=True)


async def rescan_repos(info: Info) -> list[types.GithubRepo]:
    """Rescan every tracked repository in the caller's organization.

    Fetches concurrently. This used to ``await`` one HTTP round-trip at a time inside an
    ``async for`` over the queryset, so the caller waited for the sum of every repo's
    latency. It also returned the queryset itself after consuming it.
    """
    organization = info.context.request.organization

    repos = [repo async for repo in for_org(models.GithubRepo, info)]

    await asyncio.gather(*(_rescan_one(repo, organization) for repo in repos))

    return repos
