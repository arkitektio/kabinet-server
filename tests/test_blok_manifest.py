"""Coherence of a v2 blok manifest (blok language v2): one `<Blok kind=... context=...>` root,
unique ids, roots its kind reads, declared dependencies, the locals and queries declared as nodes
of its tree, and records; refused with the vocabulary's code."""

import pytest
from pydantic import ValidationError

from rekuest_core.inputs import models as imodels

SELF = {"key": "self", "action_dependencies": [{"key": "move", "demand": {"arg_matches": [{"key": "to"}]}}], "state_dependencies": [{"key": "arm", "demand": {"matches": [{"key": "mode", "kind": "STRING"}]}}]}


def _prop(key: str, value: object) -> dict:
    return {"key": key, "static_value": value}


def _root(children: list[dict], kind: str = "agent", context: str = "panel") -> dict:
    return {"id": "Blok[0]", "component": "Blok", "props": [_prop("kind", kind), _prop("context", context)], "children": children}


def _blok(children: list[dict], *, kind: str = "agent", context: str = "panel", **fields: object) -> imodels.BlokImplementationInputModel:
    """An agent's blok: the children under its `<Blok>` root, sent as the context the root says."""
    return imodels.BlokImplementationInputModel.model_validate({"key": "demo", "vocab": 2, "context": context.upper(), "components": [_root(children, kind, context)], **fields})


def _text(path: str) -> list[dict]:
    return [{"id": "Blok[0]/Text[0]", "component": "Text", "props": [{"key": "text", "dynamic_value": {"path": path}}]}]


def _local(name: str, index: int = 0, **props: object) -> dict:
    """A `<local name=...>` as the parser writes it: its name declares the value it is read by."""
    return {"id": f"Blok[0]/local[{index}]", "component": "local", "props": [{"key": "name", "static_value": name, "declares_value": name}, *(_prop(key, value) for key, value in props.items())]}


def _query(name: str, document: str, **props: object) -> dict:
    return {"id": "Blok[0]/query[0]", "component": "query", "props": [_prop("name", name), _prop("service", "mikro"), _prop("document", document), *(_prop(key, value) for key, value in props.items())]}


def test_a_blok_says_which_language_it_speaks() -> None:
    with pytest.raises(ValidationError, match="vocab"):
        imodels.BlokImplementationInputModel.model_validate({"key": "demo", "components": [_root(_text("self.arm.mode"))]})
    with pytest.raises(ValidationError, match="vocab"):
        _blok(_text("self.arm.mode"), vocab=1)


def test_a_tree_is_one_blok_root_with_unique_ids_that_says_its_context_and_kind() -> None:
    with pytest.raises(ValidationError, match="one root, not 2"):
        imodels.BlokImplementationInputModel.model_validate({"key": "demo", "vocab": 2, "components": [_root([]), _root([])]})
    with pytest.raises(ValidationError, match=r"bsx\.duplicate_id"):
        _blok([{"id": "Blok[0]", "component": "Text"}])
    with pytest.raises(ValidationError, match=r"\[blok\.root\]"):
        imodels.BlokImplementationInputModel.model_validate({"key": "demo", "vocab": 2, "components": _text("then")})
    with pytest.raises(ValidationError, match="sent as a SCENE blok, but its <Blok> says PANEL"):
        imodels.BlokImplementationInputModel.model_validate({"key": "demo", "vocab": 2, "context": "SCENE", "components": [_root(_text("then"))]})
    with pytest.raises(ValidationError, match=r"\[kind\.placement\]"):
        _blok(_text("then"), kind="custom")
    # An action's logo is a LOGO an agent declares, of kind action.
    _blok([{"id": "Blok[0]/Logo[0]", "component": "Logo", "children": [{"id": "Blok[0]/Logo[0]/Circle[0]", "component": "Circle", "props": [{"key": "fill", "dynamic_value": {"path": "task.running"}}]}]}], kind="action", context="logo")


def test_an_agent_blok_reads_self_and_calls_its_declared_actions() -> None:
    call = {"key": "onClick", "declares_value": "move", "agent_call": {"dependency": "self", "operation": "move", "arguments": [{"key": "to", "value_literal": 1}]}}
    _blok([{"id": "Blok[0]/Button[0]", "component": "Button", "props": [call, {"key": "disabled", "dynamic_value": {"path": "move.running"}}]}], dependencies=[SELF])
    with pytest.raises(ValidationError, match=r"deps\.unknown_action"):
        _blok([{"id": "Blok[0]/Button[0]", "component": "Button", "props": [{"key": "onClick", "agent_call": {"dependency": "self", "operation": "fly"}}]}], dependencies=[SELF])
    with pytest.raises(ValidationError, match=r"deps\.unknown_state"):
        _blok(_text("self.legs"), dependencies=[SELF])
    with pytest.raises(ValidationError, match=r"roots\.not_in_kind"):
        _blok(_text("deps.robot.arm"), dependencies=[{"key": "robot"}])


def test_a_path_starts_at_a_root_a_local_or_a_record() -> None:
    with pytest.raises(ValidationError, match=r"roots\.unknown"):
        _blok(_text("nowhere.x"))
    _blok([_local("zoom", kind="INT", default=1), *_text("zoom")])
    _blok(_text("then"))
    with pytest.raises(ValidationError, match=r"roots\.event_outside_callback"):
        _blok(_text("event.value"))
    with pytest.raises(ValidationError, match=r"query\.unknown"):
        _blok(_text("queries.positions.value"))
    _blok([_query("positions", "query { positions { id } }"), *_text("queries.positions.status")])


def test_one_record_is_written_by_one_call() -> None:
    call = {"key": "onClick", "declares_value": "move", "agent_call": {"dependency": "self", "operation": "move", "arguments": [{"key": "to", "value_literal": 1}]}}
    twice = [{"id": "Blok[0]/Card[0]", "component": "Card", "children": [{"id": f"b{i}", "component": "Button", "props": [call]} for i in range(2)]}]
    with pytest.raises(ValidationError, match=r"into\.twice"):
        _blok(twice, dependencies=[SELF])


def test_what_a_blok_declares_is_well_formed() -> None:
    with pytest.raises(ValidationError, match=r"'task' is reserved.*\[roots\.reserved\]"):
        _blok([_local("task", kind="STRING"), *_text("args.x")])
    with pytest.raises(ValidationError, match=r"is a mutation.*\[query\.read_only\]"):
        _blok([_query("q", "mutation { a }"), *_text("args.x")])
    with pytest.raises(ValidationError, match=r"\[manifest\.catalog\]"):
        _blok(_text("args.x"), catalogs=["ui"])
    # A local's kind may be left out: it is inferred from the tree, never filled in here.
    assert imodels.BlokLocalInputModel.model_validate({"key": "zoom", "default": 1}).kind is None
    # A default that does not fit its kind is the checker's finding, not a refusal of the port.
    with pytest.raises(ValidationError, match=r"local\.default"):
        _blok([_local("zoom", kind="INT", default="1"), *_text("zoom")])


def test_a_prop_is_bound_at_most_one_way_and_unbound_is_null() -> None:
    with pytest.raises(ValidationError, match="at most one of"):
        imodels.ComponentPropInputModel(key="x", static_value=1, dynamic_value={"path": "a"})
    assert imodels.ComponentPropInputModel(key="x").static_value is None
    # A literal is kept as written: a bool stays a bool, a list a list.
    assert imodels.ComponentPropInputModel(key="persist", static_value=True).static_value is True
    assert imodels.ComponentPropInputModel(key="through", static_value=["robot"]).static_value == ["robot"]


def test_a_widget_prop_is_held_to_base_v1() -> None:
    """A widget feeds its definition's hash: its props keep the rules they had before v2."""
    widget = imodels.CustomAssignWidgetInputModel(kind="CUSTOM", component="Knob", props=[{"key": "on", "static_value": True}])
    assert widget.props is not None and widget.props[0].static_value == 1
    with pytest.raises(ValidationError, match="neither bound nor declares"):
        imodels.CustomAssignWidgetInputModel(kind="CUSTOM", component="Knob", props=[{"key": "on"}])


IMAGE_ARG = {"key": "image", "kind": "STRUCTURE", "identifier": "@mikro/image", "nullable": False}


def test_a_blok_reads_the_args_it_declares() -> None:
    blok = _blok(_text("args.image"), args=[IMAGE_ARG])
    assert blok.args[0].identifier == "@mikro/image"
    with pytest.raises(ValidationError, match=r"args\.unknown"):
        _blok(_text("args.other"), args=[IMAGE_ARG])


def test_only_a_panel_blok_takes_args_each_keyed_once() -> None:
    with pytest.raises(ValidationError, match="only a panel blok takes args, not a SCENE blok"):
        _blok([{"id": "Blok[0]/Scene[0]", "component": "Scene"}], context="scene", args=[IMAGE_ARG])
    with pytest.raises(ValidationError, match="Blok manifest args: duplicate key 'image'"):
        _blok(_text("args.image"), args=[IMAGE_ARG, IMAGE_ARG])


def test_an_action_blok_names_only_the_actions_dependencies() -> None:
    space = {"id": "Blok[0]/Space[0]", "component": "Space", "props": [_prop("room", "lab")], "children": [{"id": "a", "component": "Placed", "props": [_prop("dep", "crane")]}]}
    blok = imodels.ActionBlokInputModel.model_validate({"context": "SCENE", "vocab": 2, "components": [_root([space], kind="action", context="scene")]})
    with pytest.raises(ValueError, match=r"Placed.dep: 'crane' is not a dependency of the blok .*\[deps.unknown\]"):
        imodels.check_action_blok(blok, [imodels.AgentDependencyInputModel(key="robot")])
