import re
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Literal, Optional
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
    entrypoint: Optional[str] = None
    """The entrypoint the image starts the app with; None means the default, 'app'."""

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


_CAMEL = re.compile(r"(?<!^)(?=[A-Z])")


def _snake_case_keys(value: object) -> object:
    """Recursively rename camelCase dict keys to snake_case (values untouched)."""
    if isinstance(value, dict):
        return {_CAMEL.sub("_", key).lower() if isinstance(key, str) else key: _snake_case_keys(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_snake_case_keys(item) for item in value]
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

    @field_validator("inspection", mode="before")
    @classmethod
    def _snake_case_inspection(cls, value: object) -> object:
        """Config files write the inspection in camelCase (``portGroups``, ``isDev``, ``isTestFor``).

        ``rekuest_core`` models read snake_case and now forbid unknown keys, so the camelCase
        variants -- which used to be dropped silently -- are renamed before validation. Data
        arriving through GraphQL is already snake_case; renaming is a no-op there.
        """
        return _snake_case_keys(value)

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


class ReleaseFlavourModel(BaseModel):
    """One flavour of a release descriptor: an image named by digest, and where it may run."""

    name: str
    description: str | None = None
    image: str
    platforms: list[str] = Field(default_factory=list)
    selectors: list[SelectorInputModel] = Field(default_factory=list)
    inspection: InspectionInputModel
    built_at: datetime.datetime | None = None

    @field_validator("image")
    @classmethod
    def _pinned(cls, value: str) -> str:
        if "@sha256:" not in value:
            raise ValueError(f"A flavour's image is named by digest, and '{value}' is not.")
        return value

    @field_validator("inspection", mode="before")
    @classmethod
    def _snake_case_inspection(cls, value: object) -> object:
        """Descriptors write the inspection in camelCase, as `deployments.yaml` did."""
        return _snake_case_keys(value)

    def to_app_image(self, manifest: ManifestInputModel) -> AppImageInputModel:
        """The app image this flavour is, in the shape the catalogue is written from."""
        return AppImageInputModel(
            flavour_name=self.name,
            manifest=manifest,
            selectors=self.selectors,
            # The digest is the one thing that names this build and nothing else.
            app_image_id=self.image.rsplit("@sha256:", 1)[1],
            inspection=self.inspection,
            image=DockerImageModel(image_string=self.image, build_at=self.built_at),
        )


class ReleaseDescriptorModel(BaseModel):
    """A release as its registry repository carries it (the format is arkitekt-spec's ``release``).

    Unknown keys are ignored, so a newer producer can add a field. A change this reader must
    not survive arrives as another ``spec_version``, which fails validation here.
    """

    spec_version: Literal[1] = 1
    manifest: ManifestInputModel
    channel: str | None = None
    revision: str | None = None
    source: str | None = None
    flavours: list[ReleaseFlavourModel] = Field(default_factory=list)
