"""``createAppImage`` and the fields that used to be un-executable.

``createAppImage`` was a stub -- ``del parsed`` then ``return None`` under a non-null
``Release!`` -- so every call errored while the field stayed in the published schema.
Nothing covered it, which is why it could stay that way. The work it needs is
``bridge.repo.db.upsert_app_image``, shared with the repo-scanning path.

"""

import pytest
import yaml
from kante.context import HttpContext

from tests.utils import build_relative_dir, execute, execute_raw

CREATE_APP_IMAGE = """
    mutation CreateAppImage($input: AppImageInput!) {
        createAppImage(input: $input) {
            id
            version
            app { identifier }
            flavours { id name repo { id } requirements { key service } }
        }
    }
"""


def _app_image_input() -> dict:
    """A minimal, valid ``AppImageInput`` for the app in the deployments.yaml fixture.

    The manifest, image and requirements are taken from the checked-in fixture -- the same
    file ``parse_config`` is exercised against -- but ``implementations`` is emptied, and
    that is a finding rather than a convenience.

    **The fixture cannot be submitted through GraphQL as it stands.** Its port definitions
    use ``assignWidget``, while ``ArgPortInput``/``ReturnPortInput`` in ``rekuest_core``
    declare the field as ``widget``, and its definitions carry no ``version``, which
    ``DefinitionInput`` requires (``String!``). The pydantic models behind those same
    inputs are laxer on both counts, which is why ``parse_config`` swallows the file
    happily while ``createAppImage`` rejects it -- the GraphQL input layer and the
    pydantic layer it wraps have drifted apart.

    Covering implementations end-to-end therefore needs that drift resolved first (see
    the ``rekuest_core`` resync note in the plan); until then this test covers the
    catalogue-building path -- app, release, image, flavour -- which is what
    ``createAppImage`` was returning None instead of doing.
    """
    with open(build_relative_dir("deployments/deployments.yaml")) as f:
        app_image = yaml.safe_load(f)["app_images"][0]

    app_image["inspection"]["implementations"] = []
    return app_image


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_app_image_builds_the_catalogue(authenticated_context: HttpContext):
    """A pushed app image creates its app, release and flavour, and returns the release."""
    payload = _app_image_input()

    release = (await execute(CREATE_APP_IMAGE, authenticated_context, {"input": payload}))["createAppImage"]

    assert release["app"]["identifier"] == payload["manifest"]["identifier"]
    assert release["version"] == payload["manifest"]["version"]

    flavours = release["flavours"]
    assert len(flavours) == 1, flavours
    assert flavours[0]["name"] == payload["flavourName"]

    # No source repository: this image was pushed from a build, not discovered by a scan.
    # `Flavour.repo` was a non-null FK and a non-null GraphQL field until this path
    # existed, which is the reason both are nullable now.
    assert flavours[0]["repo"] is None

    # `Flavour.requirements` resolves. The model default was `dict`, and iterating a dict
    # yields its keys, so `Requirement(**"some-key")` used to raise TypeError.
    assert isinstance(flavours[0]["requirements"], list)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_app_image_is_idempotent(authenticated_context: HttpContext):
    """Pushing the same image twice updates rather than duplicating."""
    payload = _app_image_input()

    first = (await execute(CREATE_APP_IMAGE, authenticated_context, {"input": payload}))["createAppImage"]
    second = (await execute(CREATE_APP_IMAGE, authenticated_context, {"input": payload}))["createAppImage"]

    assert first["id"] == second["id"]
    assert len(second["flavours"]) == 1


FLAVOUR_BLOKS = """
    mutation CreateAppImage($input: AppImageInput!) {
        createAppImage(input: $input) {
            flavours { bloks }
        }
    }
"""


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_app_image_persists_bloks(authenticated_context: HttpContext) -> None:
    """Blok manifests in the inspection are stored on the flavour instead of being validated and dropped."""
    payload = _app_image_input()
    payload["inspection"]["bloks"] = [{"key": "demo", "components": [{"id": "root", "component": "Text"}]}]

    release = (await execute(FLAVOUR_BLOKS, authenticated_context, {"input": payload}))["createAppImage"]

    bloks = release["flavours"][0]["bloks"]
    assert len(bloks) == 1
    assert bloks[0]["key"] == "demo"
    assert bloks[0]["components"][0]["component"] == "Text"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_app_image_persists_definition_kind_and_port_groups(authenticated_context: HttpContext) -> None:
    """Definitions used to be stored with an empty kind (unservable as the ActionKind enum) and no port groups."""
    from bridge.models import Definition

    payload = _app_image_input()
    payload["inspection"]["implementations"] = [
        {
            "interface": "scan",
            "definition": {
                "key": "scan",
                "version": "1",
                "name": "Scan",
                "kind": "GENERATOR",
                "pure": True,
                "args": [{"key": "exposure", "kind": "FLOAT", "nullable": False}],
                "returns": [],
                "portGroups": [{"key": "camera", "ports": ["exposure"]}],
            },
        }
    ]

    await execute(CREATE_APP_IMAGE, authenticated_context, {"input": payload})

    definition = await Definition.objects.aget(name="Scan")
    assert definition.kind == "GENERATOR"
    assert definition.pure is True
    assert definition.port_groups[0]["key"] == "camera"
