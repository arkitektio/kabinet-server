from pydantic import BaseModel, Field, validator
from typing import List, Optional
from typing import Any
import datetime
import semver
from bridge.repo.selectors import Selector
import uuid
from rekuest_core.inputs.models import DefinitionInputModel


class Manifest(BaseModel):
    identifier: str
    version: str
    author: str
    logo: Optional[str]
    scopes: List[str]
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)

    @validator("version", pre=True)
    def version_must_be_semver(cls, v: Any) -> str:
        """Checks that the version is a valid semver version"""
        if isinstance(v, str):
            try:
                semver.VersionInfo.parse(v)
            except ValueError:
                raise ValueError("Version must be a valid semver version")
        return str(v)

    def to_console_string(self) -> str:
        return f"📦 {self.identifier} ({self.version}) by {self.author}"

    class Config:
        validate_assignment = True


class Inspection(BaseModel):
    size: int
    definitions: List[DefinitionInputModel]


class Deployment(BaseModel):
    """A deployment is a Release of a Build.
    It contains the build_id, the manifest, the builder, the definitions, the image and the deployed_at timestamp.



    """

    deployment_run: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="The unique identifier of the deployment run",
    )

    deployment_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="The unique identifier of the deployment",
    )
    manifest: Manifest = Field(description="The manifest of the app that was deployed")
    selectors: List[Selector] = Field(
        description="The selectors are used to place this image on the nodes",
        default_factory=list,
    )
    flavour: str = Field(
        description="The flavour that was used to build this deployment",
        default="vanilla",
    )
    build_id: str = Field(
        description="The build_id of the build that was deployed. Is referenced in the build.yaml file."
    )
    image: str = Field(
        description="The docker image that was built for this deployment"
    )
    deployed_at: datetime.datetime = Field(
        default_factory=datetime.datetime.now,
        description="The timestamp of the deployment",
    )
    inspection: Optional[Inspection] = Field(
        description="The inspection of the deployment",
        default=None,
    )


class DeploymentsConfigFile(BaseModel):
    """The ConfigFile is a pydantic model that represents the deployments.yaml file


    Parameters
    ----------
    BaseModel : _type_
        _description_
    """

    deployments: List[Deployment] = []
    latest_deployment_run: Optional[str] = None
