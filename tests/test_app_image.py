"""``createAppImage`` and the fields that used to be un-executable.

``createAppImage`` was a stub -- ``del parsed`` then ``return None`` under a non-null
``Release!`` -- so every call errored while the field stayed in the published schema.
Nothing covered it, which is why it could stay that way. The work it needs is
``bridge.repo.db.upsert_app_image``, shared with the repo-scanning path.

``matchFlavour`` is here for the same reason: it was declared non-null while its body has
always ended in ``.first()``, so the ordinary "nothing matched" answer came back as a
non-null violation instead of as null.
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

MATCH_FLAVOUR = """
    query MatchFlavour($input: MatchFlavoursInput!) {
        matchFlavour(input: $input) { id name }
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


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_match_flavour_finds_a_flavour(authenticated_context: HttpContext, built_chain: dict):
    """A release that exists matches its flavour."""
    from bridge.models import Flavour

    flavour = await Flavour.objects.aget(id=built_chain["flavour_id"])

    matched = (
        await execute(MATCH_FLAVOUR, authenticated_context, {"input": {"release": str(flavour.release_id)}})
    )["matchFlavour"]

    assert matched["id"] == built_chain["flavour_id"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_match_flavour_returns_null_when_nothing_matches(authenticated_context: HttpContext, built_chain: dict):
    """No match is null, not an error.

    Declared ``Flavour!`` until now, so this -- the answer a matcher exists to give --
    came back as "Cannot return null for non-nullable field".
    """
    result = await execute_raw(
        MATCH_FLAVOUR,
        authenticated_context,
        {"input": {"actions": ["0000000000000000000000000000000000000000000000000000000000000000"]}},
    )

    assert not result.errors, result.errors
    assert result.data == {"matchFlavour": None}
