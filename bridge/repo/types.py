import datetime
from typing import List, Optional
from strawberry.experimental import pydantic
from rekuest_core.inputs.types import BlokImplementationInput, ImplementationInput, StateImplementationInput, LockImplementationInput
import strawberry
from kante.unions import merged_input, union_member, union_member_types

from . import selectors
from .models import (
    DockerImageModel,
    AppImageInputModel,
    ManifestInputModel,
    InspectionInputModel,
    RequirementInputModel,
)


# The members are the SAME pydantic models that are stored on the Flavour and
# served back on Flavour.selectors (bridge/repo/selectors.py) — input, storage
# and output cannot drift. Every member exposes the shared required/weight
# hard/soft split alongside its own fields.


@union_member("SelectorInput", key="cpu")
@pydantic.input(selectors.CpuSelector)
class CpuSelectorInput:
    kind: str
    required: bool
    weight: int
    min_count: int | None = None
    frequency: float | None = None
    arch: str | None = None


@union_member("SelectorInput", key="ram")
@pydantic.input(selectors.RamSelector)
class RamSelectorInput:
    kind: str
    required: bool
    weight: int
    min: int | None = None


@union_member("SelectorInput", key="cuda")
@pydantic.input(selectors.CudaSelector)
class CudaSelectorInput:
    kind: str
    required: bool
    weight: int
    compute_capability: str | None = None
    cuda_version: str | None = None
    memory: int | None = None
    count: int | None = None
    cuda_cores: int | None = None


@union_member("SelectorInput", key="rocm")
@pydantic.input(selectors.RocmSelector)
class RocmSelectorInput:
    kind: str
    required: bool
    weight: int
    api_version: str | None = None
    api_thing: str | None = None


@union_member("SelectorInput", key="oneapi")
@pydantic.input(selectors.OneApiSelector)
class OneApiSelectorInput:
    kind: str
    required: bool
    weight: int
    oneapi_version: str | None = None


@union_member("SelectorInput", key="label")
@pydantic.input(selectors.LabelSelector)
class LabelSelectorInput:
    kind: str
    required: bool
    weight: int
    key: str
    value: str | None = None


@merged_input(
    members=[
        CpuSelectorInput,
        RamSelectorInput,
        CudaSelectorInput,
        RocmSelectorInput,
        OneApiSelectorInput,
        LabelSelectorInput,
    ],
    noun="selector",
    description="A hardware or capability requirement a backend must satisfy to run a flavour, as a discriminated union. required=true is a hard constraint; required=false is a preference scored by weight. Service dependencies are Requirements, never selectors.",
    descriptions={
        "kind": "The discriminator identifying which kind of selector this is ('cpu', 'ram', 'cuda', 'rocm', 'oneapi' or 'label')."
    },
    spec=selectors.Selector,
)
class SelectorInput:
    """One hardware/capability requirement of a flavour, discriminated by ``kind``."""


selector_types = union_member_types(SelectorInput)


@pydantic.input(RequirementInputModel)
class RequirementInput:
    key: str
    service: str
    optional: bool = False
    description: Optional[str] = None


@pydantic.input(InspectionInputModel)
class InspectionInput:
    locks: List[LockImplementationInput] = strawberry.field(description="The locks are a list of lock implementations that the app provides")
    states: List[StateImplementationInput] = strawberry.field(description="The states are a list of state implementations that the app provides")
    implementations: List[ImplementationInput] = strawberry.field(description="The implementations are a list of functionality the the app will provide")
    requirements: List[RequirementInput] = strawberry.field(description="The requirements are a list of services that the app needs to connect to (think: mikro, rekuest, ettc..)")
    bloks: list[BlokImplementationInput] = strawberry.field(description="The bloks are a list of Blok implementations that the app provides")
    size: Optional[int] = strawberry.field(description="The size of the app in MB")


@pydantic.input(ManifestInputModel)
class ManifestInput:
    """The manifest of the app that was deployed"""

    identifier: str = strawberry.field(description="The identifier of the app (should be world unique and reverse domain notation) e.g. live.arkitekt.app_name)")
    version: str = strawberry.field(description="The semver version of the app")
    author: str = strawberry.field(description="The author of the app")
    logo: str | None = strawberry.field(description="The logo of the app")
    scopes: list[str] = strawberry.field(description="A list of required scopes for the app")
    entrypoint: str | None = strawberry.field(description="The entrypoint of the app, defaults to 'app'")


@pydantic.input(DockerImageModel)
class DockerImageInput:
    image_string: str = strawberry.field(description="The identifier of the docker image")
    build_at: datetime.datetime = strawberry.field(description="The timestamp of the build")


@pydantic.input(AppImageInputModel, description="Input describing a built app image to register (its manifest, image, selectors and inspection).")
class AppImageInput:
    """Input describing a built app image to register."""

    flavour_name: str | None = strawberry.field(description="The flavour name associated with this deployment")
    manifest: ManifestInput
    selectors: list[SelectorInput] = strawberry.field(description="The selectors are used to place this image on the actions")
    app_image_id: str = strawberry.field(description="The unique identifier for the app_image")
    inspection: InspectionInput = strawberry.field(description="The inspection of the app that was deployed")
    image: DockerImageInput = strawberry.field(description="The docker image of the app that was deployed")
