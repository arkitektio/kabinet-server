from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional
from typing import Any
import datetime
import semver
from bridge.repo.selectors import Selector
import uuid
from rekuest_core.inputs.models import DefinitionInputModel, TemplateInputModel
from typing import Literal, Union

class RequirementInputModel(BaseModel):
    key: str
    service: str
    """ The service is the service that will be used to fill the key, it will be used to find the correct instance. It needs to fullfill
    the reverse domain naming scheme"""
    optional: bool = False 
    """ The optional flag indicates if the requirement is optional or not. Users should be able to use the client even if the requirement is not met. """
    description: Optional[str] = None
    """ The description is a human readable description of the requirement. Will be show to the user when asking for the requirement."""


class RocmSelectorInputModel(BaseModel):
    kind: Literal["rocm"] 
    api_version: str = Field(alias="apiVersion")
    api_thing: str = Field(alias="apiThing")

    class Config:
        allow_population_by_field_name = True


class CudaSelectorInputModel(BaseModel):
    kind: Literal["cuda"] 
    cuda_version: str = Field(alias="cudaVersion")
    cuda_cores: int = Field(alias="cudaCores")

    class Config:
        allow_population_by_field_name = True


SelectorInputModel = Union[
    CudaSelectorInputModel,
    RocmSelectorInputModel
]




class ManifestInputModel(BaseModel):
    identifier: str
    version: str
    author: str = "unknown"
    logo: Optional[str]
    scopes: List[str]
    """ The requirements are a list of requirements that the client needs to run on (e.g. needs GPU)"""


    def to_console_string(self) -> str:
        return f"📦 {self.identifier} ({self.version}) by {self.author}"

    class Config:
        validate_assignment = True


class InspectionInputModel(BaseModel):
    size: int
    templates: List[TemplateInputModel]
    requirements: List[RequirementInputModel]


class DockerImageModel(BaseModel):
    image_string: str  = Field(alias="imageString")
    build_at: datetime.datetime | None = Field(alias="buildAt")



class AppImageInputModel(BaseModel):
    """A deployment is a Release of a Build.
    It contains the build_id, the manifest, the builder, the definitions, the image and the deployed_at timestamp.



    """

    flavour_name: str | None  = Field(alias="flavourName")
    manifest: ManifestInputModel
    selectors: list[SelectorInputModel] 
    app_image_id: str = Field(alias="appImageId")
    inspection: InspectionInputModel 
    image: DockerImageModel





class KabinetConfigFile(BaseModel):
    """The ConfigFile is a pydantic model that represents the deployments.yaml file


    Parameters
    ----------
    BaseModel : _type_
        _description_
    """

    app_images: List[AppImageInputModel] = []
    latest_app_image: Optional[str] = None
