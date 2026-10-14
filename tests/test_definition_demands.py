"""`DefinitionFilter.demands` asks what rekuest's action search asks: a port's shape, and whether
the selected object meets the port's `requires`.

A demand's `descriptors` are the descriptors of a concrete object (what the menu has selected);
a definition matches only if the port they land on accepts that object. They, `nullable` and
`dimension` used to be dropped without a word, so the install list offered every definition of
the right shape. The constraint semantics are rekuest's (`facade.descriptors`): the operator
table here is the one its jsonpath compiler implements.
"""

import uuid

import pytest
from asgiref.sync import sync_to_async
from kante.context import HttpContext

from bridge.models import Definition
from tests.utils import execute

FILTERED = "query($f: DefinitionFilter){ definitions(filters: $f){ name } }"


def _port(key: str, identifier: str | None = None, kind: str = "STRUCTURE", requires: list | None = None, **extra) -> dict:
    return {"key": key, "kind": kind, "identifier": identifier, "nullable": False, "requires": requires, **extra}


@sync_to_async
def _definition(ctx: HttpContext, name: str, args: list | None = None, returns: list | None = None) -> Definition:
    return Definition.objects.create(name=name, hash=uuid.uuid4().hex, organization=ctx.request.organization, args=args or [], returns=returns or [])


async def _names(ctx: HttpContext, demands: list[dict]) -> set[str]:
    data = await execute(FILTERED, ctx, {"f": {"demands": demands}})
    return {d["name"] for d in data["definitions"]}


def _args(*matches: dict) -> dict:
    return {"kind": "ARGS", "matches": list(matches)}


def _image(at: int = 0, **descriptors) -> dict:
    match = {"at": at, "kind": "STRUCTURE", "identifier": "@mikro/image"}
    if descriptors:
        match["descriptors"] = [{"key": key, "value": value} for key, value in descriptors.items()]
    return match


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_descriptors_narrow_to_the_ports_that_accept_the_object(authenticated_context: HttpContext) -> None:
    """A definition is offered only when its port's `requires` holds for the selected object."""
    ctx = authenticated_context
    await _definition(ctx, "Any image", [_port("image", "@mikro/image")])
    await _definition(ctx, "Channel image", [_port("image", "@mikro/image", requires=[{"key": "axes", "operator": "EQUALS", "value": "c"}])])
    await _definition(ctx, "3D image", [_port("image", "@mikro/image", requires=[{"key": "@mikro/n_space_axes", "operator": "GTE", "value": 3}])])
    await _definition(ctx, "A table", [_port("table", "@mikro/table")])

    # Structural only: every image definition, as before.
    assert await _names(ctx, [_args(_image())]) == {"Any image", "Channel image", "3D image"}
    # A 2D channel image: the 3D one refuses it.
    assert await _names(ctx, [_args(_image(axes="c", **{"@mikro/n_space_axes": 2}))]) == {"Any image", "Channel image"}
    # A 3D image without channels.
    assert await _names(ctx, [_args(_image(axes="z", **{"@mikro/n_space_axes": 3}))]) == {"Any image", "3D image"}
    # A required key the object does not state is not met.
    assert await _names(ctx, [_args(_image(other=1))]) == {"Any image"}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_operators_follow_rekuest(authenticated_context: HttpContext) -> None:
    """Every operator answers as rekuest's compiled JSONPath does, a missing key included."""
    ctx = authenticated_context
    table = {
        "in": {"key": "axes", "operator": "IN", "value": ["c", "z"]},
        "not in": {"key": "axes", "operator": "NOT_IN", "value": ["c", "z"]},
        "not equals": {"key": "axes", "operator": "NOT_EQUALS", "value": "c"},
        "contains": {"key": "tags", "operator": "CONTAINS", "value": "x"},
        "exists": {"key": "axes", "operator": "EXISTS", "value": True},
        "absent": {"key": "axes", "operator": "EXISTS", "value": False},
        "at most": {"key": "n", "operator": "LTE", "value": 3},
    }
    for name, constraint in table.items():
        await _definition(ctx, name, [_port("image", "@mikro/image", requires=[constraint])])

    assert await _names(ctx, [_args(_image(axes="c"))]) == {"in", "exists"}
    assert await _names(ctx, [_args(_image(axes="t", n=3))]) == {"not in", "not equals", "exists", "at most"}
    assert await _names(ctx, [_args(_image(tags=["x", "y"], n=4))]) == {"contains", "absent"}
    # A number stated as a string is no number: LTE does not hold, and the query does not fail.
    assert await _names(ctx, [_args(_image(n="2"))]) == {"absent"}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_list_of_objects_is_matched_on_the_item_port(authenticated_context: HttpContext) -> None:
    """A multi-selection asks for a List of Structure, its descriptors on the child."""
    ctx = authenticated_context
    item = lambda requires=None: _port("0", "@mikro/image", requires=requires)
    await _definition(ctx, "Any images", [_port("images", kind="LIST", children=[item()])])
    await _definition(ctx, "Channel images", [_port("images", kind="LIST", children=[item([{"key": "axes", "operator": "EQUALS", "value": "c"}])])])

    child = {"at": 0, "kind": "STRUCTURE", "identifier": "@mikro/image", "descriptors": [{"key": "axes", "value": "z"}]}
    assert await _names(ctx, [_args({"at": 0, "kind": "LIST", "children": [child]})]) == {"Any images"}
    child["descriptors"] = [{"key": "axes", "value": "c"}]
    assert await _names(ctx, [_args({"at": 0, "kind": "LIST", "children": [child]})]) == {"Any images", "Channel images"}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_returns_are_matched_on_provides_and_nullable_is_asked(authenticated_context: HttpContext) -> None:
    """A return port answers with its `provides`, and a demand's `nullable` is no longer dropped."""
    ctx = authenticated_context
    await _definition(ctx, "Makes channel images", [], [{"key": "out", "kind": "STRUCTURE", "identifier": "@mikro/image", "nullable": False, "provides": [{"key": "axes", "operator": "EQUALS", "value": "c"}]}])
    await _definition(ctx, "Maybe an image", [], [{"key": "out", "kind": "STRUCTURE", "identifier": "@mikro/image", "nullable": True}])

    returns = lambda **match: {"kind": "RETURNS", "matches": [{"at": 0, "kind": "STRUCTURE", "identifier": "@mikro/image", **match}]}
    assert await _names(ctx, [returns(descriptors=[{"key": "axes", "value": "z"}])]) == {"Maybe an image"}
    assert await _names(ctx, [returns(nullable=True)]) == {"Maybe an image"}
    assert await _names(ctx, [returns(nullable=False)]) == {"Makes channel images"}


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_search_within_the_demands_finds_the_definition(authenticated_context: HttpContext) -> None:
    """What the menu sends when you type: the demands of a real array lens, its descriptors (a list among them) and a search."""
    ctx = authenticated_context
    lens = lambda: [_port("image", "@mikro/arraylens")]
    await _definition(ctx, "Measure Max", lens())
    await _definition(ctx, "Measure Sum", lens())
    await _definition(ctx, "Timeseries to Frames", [_port("image", "@mikro/arraylens", requires=[{"key": "@mikro/n_time_axes", "operator": "GTE", "value": 1}])])

    descriptors = {"@mikro/spec": ["VOLUME"], "@mikro/dtype": "uint8", "@mikro/is_whole": False, "@mikro/n_space_axes": 3, "@mikro/n_time_axes": 0}
    match = {"at": 0, "kind": "STRUCTURE", "identifier": "@mikro/arraylens", "descriptors": [{"key": key, "value": descriptors[key]} for key in sorted(descriptors)]}
    query = "query($f: DefinitionFilter, $p: OffsetPaginationInput){ definitions(filters: $f, pagination: $p){ id name description } }"

    data = await execute(query, ctx, {"f": {"demands": [_args(match)]}, "p": {"limit": 12}})
    assert {d["name"] for d in data["definitions"]} == {"Measure Max", "Measure Sum"}
    data = await execute(query, ctx, {"f": {"demands": [_args(match)], "search": "measure max"}, "p": {"limit": 12}})
    assert data["definitions"][0]["name"] == "Measure Max"
