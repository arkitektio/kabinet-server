from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional
import datetime
from rekuest_core.inputs.models import ImplementationInputModel, StateImplementationInputModel, LockImplementationInputModel, BlokImplementationInputModel

from .selectors import Selector


class RequirementInputModel(BaseModel):
    key: str
    service: str
    """ The service is the service that will be used to fill the key, it will be used to find the correct instance. It needs to fullfill
    the reverse domain naming scheme"""
    optional: bool = False
    """ The optional flag indicates if the requirement is optional or not. Users should be able to use the client even if the requirement is not met. """
    description: Optional[str] = None
    """ The description is a human readable description of the requirement. Will be show to the user when asking for the requirement."""


# Selectors have ONE model set for input, storage and output — see
# bridge/repo/selectors.py. The alias below keeps the historic name the rest
# of this module uses.
SelectorInputModel = Selector


class ManifestInputModel(BaseModel):
    identifier: str
    version: str
    author: str = "unknown"
    logo: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)
    """ The requirements are a list of requirements that the client needs to run on (e.g. needs GPU)"""

    def to_console_string(self) -> str:
        return f"📦 {self.identifier} ({self.version}) by {self.author}"

    model_config = ConfigDict(validate_assignment=True)


class InspectionInputModel(BaseModel):
    size: int
    locks: List[LockImplementationInputModel] = Field(alias="locks")
    implementations: List[ImplementationInputModel] = Field(alias="implementations")
    states: List[StateImplementationInputModel] = Field(alias="states")
    bloks: list[BlokImplementationInputModel] = Field(default_factory=list, alias="bloks")
    requirements: List[RequirementInputModel]


class DockerImageModel(BaseModel):
    image_string: str = Field(alias="imageString")
    build_at: datetime.datetime | None = Field(alias="buildAt")

    model_config = ConfigDict(validate_by_name=True)

    @field_validator("build_at")
    @classmethod
    def _ensure_timezone_aware(cls, value: datetime.datetime | None) -> datetime.datetime | None:
        """Treat tz-naive build timestamps as UTC so Django (USE_TZ=True) accepts them."""
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=datetime.timezone.utc)
        return value


class AppImageInputModel(BaseModel):
    """A deployment is a Release of a Build.
    It contains the build_id, the manifest, the builder, the definitions, the image and the deployed_at timestamp.



    """

    flavour_name: str | None = Field(alias="flavourName")
    manifest: ManifestInputModel
    selectors: list[SelectorInputModel]
    app_image_id: str = Field(alias="appImageId")
    inspection: InspectionInputModel
    image: DockerImageModel

    model_config = ConfigDict(validate_by_name=True)

    @field_validator("selectors", mode="before")
    @classmethod
    def _coerce_selectors(cls, value: object) -> object:
        """Normalise selectors to dicts so the discriminated union can resolve them.

        ``AppImageInput.to_pydantic()`` already yields the correct member models
        (kante's merged ``SelectorInput`` dispatches by ``kind``), but selectors
        also arrive from config files and older callers as dicts or foreign
        model instances; pydantic will not coerce a model instance into a
        different union member, but it will coerce a dict (matched on ``kind``).
        """
        if not isinstance(value, (list, tuple)):
            return value
        normalised = []
        for selector in value:
            if isinstance(selector, BaseModel):
                selector = selector.model_dump(exclude_none=True)
            normalised.append(selector)
        return normalised


class KabinetConfigFile(BaseModel):
    """The ConfigFile is a pydantic model that represents the deployments.yaml file


    Parameters
    ----------
    BaseModel : _type_
        _description_
    """

    app_images: List[AppImageInputModel] = []
    latest_app_image: Optional[str] = None
