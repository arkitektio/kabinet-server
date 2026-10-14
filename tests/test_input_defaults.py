"""Every nullable input field has a default.

GraphQL lets a client leave a nullable input field out entirely, and the kabinet
client does (it sends only the fields that were set). A strawberry input whose
``X | None`` field has no default then fails in its generated ``__init__`` with
"missing 1 required keyword-only argument" -- a server error for a valid request.
``UpdatePodInput.pod`` and ``ManifestInput.entrypoint`` both shipped that way, and
each was found only by a client in the lab. This walks every input in the schema.
"""

import dataclasses

from strawberry.types.base import StrawberryObjectDefinition, StrawberryOptional


def test_every_nullable_input_field_has_a_default():
    from kabinet_server.schema import schema

    missing = []
    for name, converted in schema.schema_converter.type_map.items():
        definition = converted.definition
        if not (isinstance(definition, StrawberryObjectDefinition) and definition.is_input):
            continue
        for field in definition.fields:
            if (
                isinstance(field.type, StrawberryOptional)
                and field.default is dataclasses.MISSING
                and field.default_factory is dataclasses.MISSING
            ):
                missing.append(f"{name}.{field.python_name}")

    assert not missing, (
        "These nullable input fields have no default, so a client omitting them gets a "
        f"server error; give each `= None`: {', '.join(sorted(missing))}"
    )
