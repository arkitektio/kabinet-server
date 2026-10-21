"""An inspected release whose actions carry protocol hints is read, not refused.

The vendored ``rekuest_core`` models forbid unknown keys, so a field the rekuest service
learned has to be learned here too, or every release that hints is refused at import.
"""

from bridge.repo.models import InspectionInputModel


def inspection(**definition: object) -> dict:
    base = {"key": "attach", "version": "1", "name": "Attach", "kind": "FUNCTION", "args": [], "returns": []}
    return {
        "requirements": [],
        "locks": [],
        "states": [],
        "implementations": [{"interface": "attach", "definition": {**base, **definition}}],
    }


def test_an_action_with_protocol_hints_is_read() -> None:
    model = InspectionInputModel.model_validate(inspection(protocols=["on_scene_init"]))
    assert model.implementations[0].definition.protocols == ["on_scene_init"]


def test_an_action_without_them_is_read_as_before() -> None:
    model = InspectionInputModel.model_validate(inspection())
    assert model.implementations[0].definition.protocols == []
