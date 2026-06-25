from kante.types import Info
from bridge import types, inputs, models
import logging
from typing import List

logger = logging.getLogger(__name__)


async def match_flavours(
    info: Info, input: inputs.MatchFlavoursInput
) -> List[types.Flavour]:
    """Return the flavours matching the requested release."""
    parsed = input.to_pydantic()

    flavour = models.Flavour.objects.filter(id=parsed.release)

    return flavour
