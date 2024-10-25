import datetime
from typing import List, Optional
from strawberry.experimental import pydantic
from rekuest_core.inputs.types import TemplateInput
import strawberry
from .models import DockerImageModel, AppImageInputModel, ManifestInputModel, InspectionInputModel, RequirementInputModel
from ..directives import unionElementOf


@strawberry.input(directives=[unionElementOf(union="SelectorInput", discriminator="kind", key="rocm")])
class RocmSelectorInput:
    api_version: str = strawberry.field(description="The api version of the selector")
    api_thing: str = strawberry.field(description="The api thing of the selector")


@strawberry.input(directives=[unionElementOf(union="SelectorInput", discriminator="kind", key="cuda")])
class CudaSelectorInput:
    cuda_version: str = strawberry.field(description="The minimum cuda version")
    cuda_cores: int = strawberry.field(description="The cuda cores")



@strawberry.input(directives=[unionElementOf(union="SelectorInput", discriminator="kind", key="cpu")])
class CpuSelector:
    frequency: int = strawberry.field(description="The frequency in MHz")
    memory: int = strawberry.field(description="The memory in MB")

@strawberry.input(directives=[])
class SelectorInput:
    kind: str = strawberry.field(description="The kind of the selector")
    api_version: str = strawberry.field(description="The api version of the selector")
    api_thing: str = strawberry.field(description="The api thing of the selector")
    cuda_cores: int = strawberry.field(description="The cuda cores")




selector_types = [CudaSelectorInput, RocmSelectorInput, CpuSelector]




@pydantic.input(RequirementInputModel)
class RequirementInput:
    key: str
    service: str
    optional: bool = False 
    description: Optional[str] = None


@pydantic.input(InspectionInputModel)
class InspectionInput:
    templates: List[TemplateInput] = strawberry.field(description="The templates are a list of functionality the the app will provide")
    requirements: List[RequirementInput] = strawberry.field(description="The requirements are a list of services that the app needs to connect to (think: mikro, rekuest, ettc..)")

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

 

@pydantic.input(AppImageInputModel, description="Create a new Github repository input")
class AppImageInput:
    """Create a new Github repository input"""
    flavour_name: str | None = strawberry.field(description="The flavour name associated with this deployment")
    manifest: ManifestInput
    selectors: list[SelectorInput] = strawberry.field(description="The selectors are used to place this image on the nodes")
    app_image_id: str = strawberry.field(description="The unique identifier for the app_image")
    inspection: InspectionInput = strawberry.field(description="The inspection of the app that was deployed")
    image: DockerImageInput = strawberry.field(description="The docker image of the app that was deployed")