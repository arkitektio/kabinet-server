"""A flavour's bloks, parsed and served ready to draw: its logo, its actions' logos and the rest.

An app sends its bloks as BSX ``source``. ``Flavour.bloks`` keeps them as sent; the import parses
each into the tree a client renders (``Flavour.blok_renders``) and notes which blok draws each
action (``Flavour.action_logos``). ``restore_bloks`` does both for flavours imported before.
"""

import copy

import pytest
import yaml
from asgiref.sync import sync_to_async
from django.core.management import call_command
from kante.context import HttpContext

from bridge import models
from bridge.repo import bloks
from bridge.repo.db import upsert_app_image
from bridge.repo.models import AppImageInputModel
from tests.utils import build_relative_dir, execute

APP_LOGO = '<Blok kind="agent" context="logo"><Logo viewBox="0 0 24 24"><Circle r="4" fill="brand" /></Logo></Blok>'
ACTION_LOGO = '<Blok kind="action" context="logo"><Logo viewBox="0 0 24 24" title="Segment"><Circle r="4" fill={task.running ? "brand" : "muted"} /></Logo></Blok>'
BROKEN = '<Blok kind="agent" context="panel"><Card><Text></Card></Blok>'


def _app_image(
    *, logo: str | None = "ome_segment", version: str = "1.0.0"
) -> tuple[AppImageInputModel, str]:
    """The fixture's app image with its logo, an action logo its first action names, and a panel that does not parse."""
    with open(build_relative_dir("deployments/deployments.yaml")) as f:
        app_image = copy.deepcopy(yaml.safe_load(f)["app_images"][0])
    app_image["manifest"]["version"] = version
    implementation = app_image["inspection"]["implementations"][0]
    implementation["logo"] = logo
    app_image["inspection"]["implementations"] = [implementation]
    app_image["inspection"]["bloks"] = [
        {
            "key": "ome_logo",
            "vocab": 2,
            "context": "LOGO",
            "default": True,
            "source": APP_LOGO,
        },
        {
            "key": "ome_segment",
            "vocab": 2,
            "context": "LOGO",
            "source": ACTION_LOGO,
            "demo": {"task": {"running": True}},
        },
        {"key": "ome_broken", "vocab": 2, "context": "PANEL", "source": BROKEN},
    ]
    model = AppImageInputModel.model_validate(app_image)
    return model, model.inspection.implementations[0].definition.unique_hash


@sync_to_async
def _import(ctx: HttpContext, **kwargs) -> tuple[models.Flavour, str]:
    app_image, definition_hash = _app_image(**kwargs)
    return upsert_app_image(app_image, ctx.request.organization), definition_hash


def test_a_source_is_parsed_into_a_list_of_roots_in_the_wire_spelling() -> None:
    """The tree is what rekuest serves as `Blok.componentTree`: roots, snake_case, nothing None."""
    render = bloks.render_blok({"key": "a", "context": "LOGO", "source": ACTION_LOGO})

    assert render["parse_error"] is None
    [root] = render["component_tree"]
    assert root["component"] == "Blok"
    [logo] = root["children"]
    assert {"key": "viewBox", "static_value": "0 0 24 24"} in logo["props"]
    assert logo["children"][0]["id"] == "Blok[0]/Logo[0]/Circle[0]"
    assert bloks.root_kind(render["component_tree"]) == "action"
    assert render["hash"].startswith("sha256:")


def test_the_hash_is_what_the_blok_draws() -> None:
    """The same tree, context and declarations hash alike; a different demo does not."""
    one = bloks.render_blok({"key": "a", "context": "LOGO", "source": APP_LOGO})
    same = bloks.render_blok({"key": "b", "context": "LOGO", "source": APP_LOGO})
    other = bloks.render_blok(
        {"key": "a", "context": "LOGO", "source": APP_LOGO, "demo": {"args": {"x": 1}}}
    )

    assert one["hash"] == same["hash"]
    assert one["hash"] != other["hash"]


def test_a_source_that_does_not_parse_says_why() -> None:
    """A broken blok is the blok's problem: no tree, an error, never an exception."""
    render = bloks.render_blok({"key": "a", "context": "PANEL", "source": BROKEN})

    assert render["component_tree"] is None
    assert render["parse_error"]
    # A root that disagrees with the context it is sent as is the blok's problem too.
    assert (
        "its <Blok> says LOGO"
        in bloks.render_blok({"key": "a", "context": "PANEL", "source": APP_LOGO})[
            "parse_error"
        ]
    )


def test_a_blok_sent_as_its_tree_keeps_it() -> None:
    tree = [
        {
            "id": "Blok[0]",
            "component": "Blok",
            "props": [
                {"key": "kind", "static_value": "agent"},
                {"key": "context", "static_value": "panel"},
            ],
            "children": [{"id": "root", "component": "Text"}],
        }
    ]
    render = bloks.render_blok({"key": "a", "context": "PANEL", "components": tree})
    assert render["component_tree"] == tree and render["parse_error"] is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_an_import_renders_its_bloks_and_keeps_them_as_sent(
    authenticated_context: HttpContext,
) -> None:
    flavour, definition_hash = await _import(authenticated_context)

    assert [blok["source"] for blok in flavour.bloks] == [APP_LOGO, ACTION_LOGO, BROKEN]
    assert all(blok["components"] is None for blok in flavour.bloks)
    assert set(flavour.blok_renders) == {"ome_logo", "ome_segment", "ome_broken"}
    assert flavour.action_logos == {definition_hash: "ome_segment"}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_flavour_serves_its_bloks_and_its_logo(
    authenticated_context: HttpContext,
) -> None:
    flavour, _ = await _import(authenticated_context)

    result = (
        await execute(
            """query($id: ID!) { flavour(id: $id) {
                logoBlok { id key context default hash }
                blokImplementations { key context kind componentTree parseError }
                logos: blokImplementations(context: LOGO) { key kind vocab demo }
            } }""",
            authenticated_context,
            {"id": str(flavour.id)},
        )
    )["flavour"]

    assert result["logoBlok"]["id"] == f"{flavour.id}:ome_logo"
    assert result["logoBlok"]["default"] is True
    assert result["logoBlok"]["hash"] == flavour.blok_renders["ome_logo"]["hash"]
    by_key = {blok["key"]: blok for blok in result["blokImplementations"]}
    assert (
        by_key["ome_segment"]["componentTree"][0]["children"][0]["component"] == "Logo"
    )
    assert (
        by_key["ome_broken"]["componentTree"] is None
        and by_key["ome_broken"]["parseError"]
    )
    # An action's logo is a LOGO too: its root's kind tells it from the app's.
    _, action_logo = result["logos"]
    assert (
        action_logo["key"] == "ome_segment"
        and action_logo["kind"] == "action"
        and action_logo["vocab"] == 2
    )
    assert action_logo["demo"]["task"] == {"running": True}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_blok_is_found_by_its_id(authenticated_context: HttpContext) -> None:
    flavour, _ = await _import(authenticated_context)

    found = await execute(
        "query($id: ID!) { flavourBlok(id: $id) { key flavourId } }",
        authenticated_context,
        {"id": f"{flavour.id}:ome_segment"},
    )
    missing = await execute(
        "query($id: ID!) { flavourBlok(id: $id) { key } }",
        authenticated_context,
        {"id": f"{flavour.id}:nope"},
    )
    garbage = await execute(
        "query($id: ID!) { flavourBlok(id: $id) { key } }",
        authenticated_context,
        {"id": "nope"},
    )

    assert found["flavourBlok"] == {"key": "ome_segment", "flavourId": str(flavour.id)}
    assert missing["flavourBlok"] is None
    assert garbage["flavourBlok"] is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_release_and_its_app_serve_the_logo(
    authenticated_context: HttpContext,
) -> None:
    flavour, _ = await _import(authenticated_context)

    result = await execute(
        "query { apps { logoBlok { key } releases { logoBlok { key } } } }",
        authenticated_context,
    )

    [app] = result["apps"]
    assert app["logoBlok"] == {"key": "ome_logo"}
    assert app["releases"] == [{"logoBlok": {"key": "ome_logo"}}]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_definition_is_drawn_by_the_logo_its_implementation_names(
    authenticated_context: HttpContext,
) -> None:
    older, _ = await _import(authenticated_context, logo=None, version="0.9.0")
    newer, definition_hash = await _import(authenticated_context, version="1.0.0")

    stored = await models.Definition.objects.aget(hash=definition_hash)

    definition = (
        await execute(
            """query($id: ID!, $older: ID!, $newer: ID!) { definition(id: $id) {
                logo { id key context }
                ofOlder: logo(flavour: $older) { key }
                ofNewer: logo(flavour: $newer) { key }
            } }""",
            authenticated_context,
            {"id": str(stored.id), "older": str(older.id), "newer": str(newer.id)},
        )
    )["definition"]
    assert definition["logo"] == {
        "id": f"{newer.id}:ome_segment",
        "key": "ome_segment",
        "context": "LOGO",
    }
    assert definition["ofOlder"] is None
    assert definition["ofNewer"] == {"key": "ome_segment"}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_restore_bloks_renders_a_flavour_imported_before(
    authenticated_context: HttpContext,
) -> None:
    flavour, definition_hash = await _import(authenticated_context)
    await models.Flavour.objects.filter(id=flavour.id).aupdate(
        blok_renders={}, action_logos={}
    )

    await sync_to_async(call_command)("restore_bloks")
    await sync_to_async(call_command)("restore_bloks")

    restored = await models.Flavour.objects.aget(id=flavour.id)
    assert restored.blok_renders == flavour.blok_renders
    assert restored.action_logos == {definition_hash: "ome_segment"}
