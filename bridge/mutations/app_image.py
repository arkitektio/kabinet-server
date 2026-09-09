from asgiref.sync import sync_to_async
from kante.types import Info

from bridge import models, types
from bridge.repo.db import upsert_app_image
from bridge.repo.types import AppImageInput


async def create_app_image(info: Info, input: AppImageInput) -> types.Release:
    """Register a built app image, creating its app, release, image and flavour as needed.

    This was a stub -- `del parsed` followed by `return None` under a non-null `Release!`
    return type -- so every call errored while the field stayed in the published schema.
    The work it needed already existed as the body of `parse_config`'s loop and is now
    `upsert_app_image`, shared with the repo-scanning path.

    No repo is passed: an image pushed straight from a build has no source repository,
    which is what makes `Flavour.repo` nullable.
    """
    parsed = input.to_pydantic()

    flavour = await sync_to_async(upsert_app_image)(parsed, info.context.request.organization)

    # Fetched by id rather than through `flavour.release`: the FK descriptor would be a
    # lazy load, and `SynchronousOnlyOperation` is the reward for touching one of those
    # from an async resolver.
    return await models.Release.objects.aget(id=flavour.release_id)
