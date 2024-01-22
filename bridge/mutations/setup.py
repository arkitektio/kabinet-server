from koherent.types import Info
from bridge import types, inputs, models
from bridge.backend import get_backend
import logging

logger = logging.getLogger(__name__)

        
async def create_setup(
    info: Info, input: inputs.CreateSetupInput
) -> types.Setup:
    """ Create a new dask cluster on a bridge server"""

    installer = info.context.request.user

    backend = get_backend()

    
    if input.flavour:
        flavour = await models.Flavour.objects.aget(
            id=input.flavour
        )
    else:
        release = await models.Release.objects.aget(
            id=input.release
        )

        flavour = await backend.aget_fitting_flavour(release)



    setup = await models.Setup.objects.acreate(
        flavour=flavour,
        installer=installer,
        command=input.command,
        api_token=input.fakts_token,
        fakts_url=input.fakts_url,
    )

    return setup


async def deploy_setup(
    info: Info, input: inputs.DeploySetupInput
) -> types.Pod:
    """ Create a new dask cluster on a bridge server"""


    setup = await models.Setup.objects.prefetch_related("release").aget(
        id=input.setup
    )

    print(setup)

    backend = get_backend()

    return await backend.aup_setup(setup)
