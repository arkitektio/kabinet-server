from kante.types import Info
from bridge import types, inputs, models
import logging
from typing import List

logger = logging.getLogger(__name__)


async def match_flavours(
    info: Info, input: inputs.MatchFlavoursInput
) -> List[types.Flavour]:
    """Create a new dask cluster on a bridge server"""

    flavour = models.Flavour.objects.filter(id=input.release)

    return flavour
