from kante.types import Info
from bridge import types, inputs, models
from bridge.repo.types import AppImageInput
import logging
from typing import List


async def create_app_image(info: Info, input: AppImageInput) -> types.Release:
    """Register a built app image, creating its release and flavour as needed."""
    parsed = input.to_pydantic()
    del parsed  # TODO: persist the app image; resolver is currently a stub.
    return None
