"""A definition is in the collections its declaration names, as rekuest's action is.

The import puts it there (``store_collections``, by ``(organization, name)``, created when
missing); ``restore_collections`` does it for definitions imported before. Both are what
``DefinitionFilter.inCollection`` answers from.
"""

import copy

import pytest
import yaml
from asgiref.sync import sync_to_async
from django.core.management import call_command
from kante.context import HttpContext

from bridge import models
from bridge.repo.db import upsert_app_image
from bridge.repo.models import AppImageInputModel
from tests.utils import build_relative_dir, execute


def _app_image(collections: list[str]) -> AppImageInputModel:
    with open(build_relative_dir("deployments/deployments.yaml")) as f:
        app_image = copy.deepcopy(yaml.safe_load(f)["app_images"][0])
    implementation = app_image["inspection"]["implementations"][0]
    implementation["definition"]["collections"] = collections
    app_image["inspection"]["implementations"] = [implementation]
    return AppImageInputModel.model_validate(app_image)


@sync_to_async
def _import(ctx: HttpContext, collections: list[str]) -> models.Definition:
    app_image = _app_image(collections)
    upsert_app_image(app_image, ctx.request.organization)
    return models.Definition.objects.get(
        hash=app_image.inspection.implementations[0].definition.unique_hash,
        organization=ctx.request.organization,
    )


@sync_to_async
def _collections(definition: models.Definition) -> list[str]:
    return sorted(definition.collections.values_list("name", flat=True))


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_the_import_puts_a_definition_in_its_collections(
    authenticated_context: HttpContext,
) -> None:
    ctx = authenticated_context
    definition = await _import(ctx, ["segmentation", "processing", "segmentation"])

    assert await _collections(definition) == ["processing", "segmentation"]
    data = await execute(
        "query($f: DefinitionFilter){ definitions(filters: $f){ id } }",
        ctx,
        {"f": {"inCollection": "segmentation"}},
    )
    assert [d["id"] for d in data["definitions"]] == [str(definition.id)]

    # Another definition naming the same collection joins it rather than making a second.
    await _import(ctx, ["segmentation"])
    assert (
        await models.Collection.objects.filter(
            name="segmentation", organization=ctx.request.organization
        ).acount()
        == 1
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_restore_collections_fills_a_definition_imported_before(
    authenticated_context: HttpContext,
) -> None:
    ctx = authenticated_context
    definition = await _import(ctx, ["segmentation"])
    await sync_to_async(definition.collections.clear)()

    await sync_to_async(call_command)("restore_collections")
    await sync_to_async(call_command)("restore_collections")

    assert await _collections(definition) == ["segmentation"]
