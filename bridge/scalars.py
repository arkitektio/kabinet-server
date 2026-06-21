from typing import NewType

import strawberry

UntypedParams = NewType("UntypedParams", object)


scalar_map = {
    UntypedParams: strawberry.scalar(
        name="UntypedParams",
        description="An untyped, free-form JSON object whose shape is not known to the schema.",
        serialize=lambda v: v,
        parse_value=lambda v: v,
    ),
}
