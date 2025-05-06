from kante.types import Info
from bridge import types, inputs, models
from bridge.repo.types import AppImageInput
import logging
from typing import List


async def create_app_image(info: Info, input: AppImageInput) -> types.Release:
    """Create a new dask cluster on a bridge server"""

    return None
