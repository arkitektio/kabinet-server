from koherent.types import Info
from bridge import types, inputs, models
import logging
import aiohttp
import yaml
from bridge.repo.db import parse_config
from bridge.repo.models import KabinetConfigFile
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile

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
            z = await response.text()

    z = yaml.safe_load(z)
    if not isinstance(z, dict):
        raise Exception("Invalid kabinet.yml")
    
    print(z)

    config = KabinetConfigFile(**z)
    return config


async def scan_repo(info: Info, input: inputs.ScanRepoInput) -> types.GithubRepo:
    """Create a new dask cluster on a bridge server"""
    repo = await models.GithubRepo.objects.aget(id=input.id)

    config = await aget_kabinet_config(repo.kabinet_url)

    try:
        await parse_config(config, repo)
    except KeyError as e:
        logger.error(e, exc_info=True)
        pass

    return repo


async def create_github_repo(
    info: Info, input: inputs.CreateGithupRepoInput
) -> types.GithubRepo:
    dep_url = models.GithubRepo.build_kabinet_url(
        input.user, input.repo, input.branch
    )

    config = await aget_kabinet_config(dep_url)

    repo, _ = await models.GithubRepo.objects.aget_or_create(
        user=input.user,
        branch=input.branch,
        repo=input.repo,
        defaults=dict(
            name=input.name,
            creator=info.context.request.user,
        )

    )

    try:
        await parse_config(config, repo)
    except KeyError as e:
        logger.error(e, exc_info=True)
        pass
        raise e

    return repo


async def rescan_repos(info: Info) -> list[types.GithubRepo]:
    repos = models.GithubRepo.objects.all()

    async for repo in repos:
        config = await aget_kabinet_config(repo.kabinet_url)

        try:
            await parse_config(config, repo)
        except KeyError as e:
            logger.error(e, exc_info=True)
            pass

    return repos
