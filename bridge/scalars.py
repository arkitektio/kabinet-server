from typing import NewType

import strawberry

UntypedOptions = strawberry.scalar(
    NewType("UntypedOptions", object),
    description="UntypedOptions represents an untyped options object returned by the Dask Gateway API.",
    serialize=lambda v: v,
    parse_value=lambda v: v,
)
