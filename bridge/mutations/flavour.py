from koherent.types import Info
from bridge import types, inputs, models
from bridge.backend import get_backend
import logging

logger = logging.getLogger(__name__)

        
async def pull_flavour(
    info: Info, input: inputs.PullFlavourInput
) -> types.Flavour:
    """ Create a new dask cluster on a bridge server"""

    backend = get_backend()
    

    flavour = await models.Flavour.objects.aget(
        id=input.id
    )

    await backend.apull_flavour(flavour)

    return flavour
