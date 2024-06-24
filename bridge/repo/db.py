from rekuest_core.hash import hash_definition
from .models import KabinetConfigFile
from bridge import models
from .errors import DBError
import aiohttp
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile


async def adownload_logo(url: str) -> File:  # type: ignore
    """Downloads a logo from a url and returns a django file"""
    img_tmp = NamedTemporaryFile(delete=True)
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            img_tmp.write(await response.read())
            img_tmp.flush()

    return File(img_tmp)


async def parse_config(
    config: KabinetConfigFile, repo: models.GithubRepo
) -> list[models.Flavour]:
    """Parse a deployments config file and create models"""

    deps = []
    try:
        for deployment in config.deployments:
            print(deployment)
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

            flavour, _ = await models.Flavour.objects.aupdate_or_create(
                release=release,
                name=deployment.flavour,
                defaults=dict(
                    deployment_id=deployment.deployment_id,
                    flavour=deployment.flavour,
                    selectors=[d.dict() for d in deployment.selectors],
                    repo=repo,
                    image=deployment.image,
                ),
            )

            if deployment.templates:
                for key, template in deployment.templates.items():
                    def_model, _ = await models.Definition.objects.aupdate_or_create(
                        hash=hash_definition(template.definition),
                        defaults=dict(
                            description=template.definition.description,
                            args=[d.dict() for d in template.definition.args],
                            returns=[d.dict() for d in template.definition.returns],
                            name=template.definition.name,
                        ),
                    )
                    await def_model.flavours.aadd(flavour)

            deps.append(flavour)
    except Exception as e:
        raise DBError("Could not create models from deployments") from e

    return deps
