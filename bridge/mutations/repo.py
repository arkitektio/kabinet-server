from kante.types import Info
from bridge import types, inputs, models
import logging
import aiohttp
import yaml
from bridge.repo.db import parse_config
from bridge.repo.models import KabinetConfigFile
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
import re
from authentikate.models import Organization, User


logger = logging.getLogger(__name__)


async def adownload_logo(url: str) -> File:
    """Downloads a logo from a url and returns a django file"""
    img_tmp = NamedTemporaryFile(delete=True)
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            img_tmp.write(await response.read())
            img_tmp.flush()

    return File(img_tmp)


async def aget_kabinet_config(kabinet_url: str) -> KabinetConfigFile:
    async with aiohttp.ClientSession(headers={"Cache-Control": "no-cache"}) as session:
        async with session.get(kabinet_url) as response:
            assert response.status == 200, f"This seems to be not an Arkitekt Repository. Failed to fetch kabinet.yml."

            z = await response.text()

    z = yaml.safe_load(z)
    if not isinstance(z, dict):
        raise Exception("Invalid kabinet.yml")

    config = KabinetConfigFile(**z)
    return config


async def scan_repo(info: Info, input: inputs.ScanRepoInput) -> types.GithubRepo:
    """Scan a tracked GitHub repository for app manifests and update its flavours."""
    parsed = input.to_pydantic()
    repo = await models.GithubRepo.objects.aget(id=parsed.id)

    config = await aget_kabinet_config(repo.kabinet_url)

    try:
        await parse_config(config, repo, organization=info.context.request.organization)
    except KeyError as e:
        logger.error(e, exc_info=True)
        pass

    return repo


def infer_repo_info(input: inputs.CreateGithubRepoInputModel) -> tuple[str, str, str, str]:
    if input.identifier:
        # Check if the identifier is a full GitHub URL
        url_pattern = r"https:\/\/github\.com\/([^\/]+)\/([^\/]+)(?:\/tree\/([^\/]+))?"
        match = re.match(url_pattern, input.identifier)

        if match:
            # Extract user, repo, and optionally branch from the URL
            user, repo, branch = match.groups()
            branch = branch or "main"
        else:
            # Check if the identifier is a full GitHub URL without /tree/
            url_pattern_no_tree = r"https:\/\/github\.com\/([^\/]+)\/([^\/]+)"
            match = re.match(url_pattern_no_tree, input.identifier)
            if match:
                user, repo = match.groups()
                branch = "main"
            else:
                try:
                    assert "/" in input.identifier, "Invalid GitHub identifier"
                    user, repo = input.identifier.split("/")
                    if ":" in repo:
                        repo, branch = repo.split(":")
                    else:
                        branch = "main"

                except AssertionError as e:
                    raise Exception("Invalid GitHub identifier")

        name = f"{input.user}/{input.repo}:{branch}"
        return user, repo, branch, input.identifier

    else:
        assert input.user and input.repo, "Invalid github repo"

        if input.branch:
            branch = input.branch
        else:
            branch = "main"

        name = f"{input.user}/{input.repo}:{branch}"

        return input.user, input.repo, branch, name


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

    try:
        await parse_config(config, repo, organization)
    except KeyError as e:
        logger.error(e, exc_info=True)
        pass
        raise e

    return repo


async def create_github_repo(info: Info, input: inputs.CreateGithubRepoInput) -> types.GithubRepo:
    parsed = input.to_pydantic()
    return await _create_github_repo(parsed, info.context.request.organization, info.context.request.user)


async def rescan_repos(info: Info) -> list[types.GithubRepo]:
    repos = models.GithubRepo.objects.all()

    async for repo in repos:
        config = await aget_kabinet_config(repo.kabinet_url)

        try:
            await parse_config(config, repo, organization=info.context.request.organization)
        except KeyError as e:
            logger.error(e, exc_info=True)
            pass

    return repos
