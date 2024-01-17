from koherent.types import Info
from bridge import types, inputs, models
import logging
import aiohttp
import yaml
from bridge.repo.models import DeploymentsConfigFile
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
        
async def scan_repo(
    info: Info, input: inputs.ScanRepoInput
) -> types.GithubRepo:
    """ Create a new dask cluster on a bridge server"""
    repo = await models.GithubRepo.objects.aget(
        id=input.id
    )

    async with aiohttp.ClientSession(headers={
        "Cache-Control": "no-cache"
    }) as session:
        async with session.get(repo.deployments_url) as response:
            z = await response.text()

    z = yaml.safe_load(z)
    if not isinstance(z, dict):
        raise Exception("Invalid deployments.yml")
    

    config = DeploymentsConfigFile(**z)

    deps = []
    try:
        for deployment in config.deployments:
            manifest = deployment.manifest

            app, _ = await models.App.objects.aget_or_create(
                identifier=manifest.identifier,
            )

            release, _ = await models.Release.objects.aupdate_or_create(
                version=manifest.version,
                app=app,
                defaults=dict(
                    scopes=manifest.scopes,
                ),
            )

            if manifest.logo:
                logo_file = await adownload_logo(manifest.logo)
                release.logo.save(f"logo{release.id}.png", logo_file)
                await release.asave()


            dep, _ = await models.Flavour.objects.aupdate_or_create(
                release=release,
                name=deployment.flavour ,
                defaults=dict(
                    deployment_id=deployment.deployment_id,
                    build_id=deployment.build_id,
                    flavour=deployment.flavour,
                    selectors=[d.dict() for d in deployment.selectors],
                    repo=repo
                ),
            )

            deps.append(dep)
    except KeyError as e:
        logger.error(e, exc_info=True)
        pass





    return repo



async def create_github_repo(
        info: Info, input: inputs.CreateGithupRepoInput
) -> types.GithubRepo:
    
    return await models.GithubRepo.objects.acreate(
        name=input.name,
        user=input.user,
        branch=input.branch,
        repo=input.repo,
        creator=info.context.request.user,
    )
