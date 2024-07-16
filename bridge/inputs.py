import datetime
from pydantic import BaseModel, Field
from strawberry.experimental import pydantic
from .enums import PodStatus, ContainerType
import strawberry
from rekuest_core.scalars import NodeHash
from typing import Dict, Optional
from bridge import scalars


class ScanRepoInputModel(BaseModel):
    """Create a dask cluster input model"""

    id: str


@pydantic.input(ScanRepoInputModel, description="Create a dask cluster input")
class ScanRepoInput:
    """Create a dask cluster input"""

    id: str


class CreateGithupRepoInputModel(BaseModel):
    """Create a new Github repository input model"""
    name: str  | None = None
    user: str | None = None
    branch: str | None = None
    repo: str | None = None
    identifier: str | None = None
    auto_scan: bool = True


@pydantic.input(
    CreateGithupRepoInputModel, description="Create a new Github repository input"
)
class CreateGithupRepoInput:
    """Create a new Github repository input"""

    name: str | None = None
    user: str | None = None
    branch: str | None = None
    repo: str | None = None
    identifier: str | None = None
    auto_scan: bool | None = True


    


class PullFlavourInputModel(BaseModel):
    """Create a new Github repository input model"""

    id: str


@pydantic.input(
    PullFlavourInputModel, description="Create a new Github repository input"
)
class PullFlavourInput:
    """Create a new Github repository input"""

    id: strawberry.ID


class CreateSetupInputModel(BaseModel):
    """Create a new Github repository input model"""

    release: str
    flavour: str | None = None
    fakts_url: str | None = "lok:80"
    fakts_token: str | None = None
    command: str | None = "arkitekt prod run"
    auto_pull: bool = True


@pydantic.input(
    CreateSetupInputModel, description="Create a new Github repository input"
)
class CreateSetupInput:
    """Create a new Github repository input"""

    release: strawberry.ID
    flavour: strawberry.ID | None = None
    fakts_url: str | None = None
    fakts_token: str | None = None
    command: str | None = "arkitekt prod run"
    auto_pull: bool | None = True


class DeploySetupInputModel(BaseModel):
    """Create a new Github repository input model"""

    setup: str


@pydantic.input(
    DeploySetupInputModel, description="Create a new Github repository input"
)
class DeploySetupInput:
    """Create a new Github repository input"""

    setup: strawberry.ID





class DeviceFeatureModel(BaseModel):
    kind: str
    cpu_count: str


class EnvironmentInputModel(BaseModel):
    container_type: ContainerType
    nodes: Optional[list[str]] 
    release: Optional[str] = None
    fits: list[DeviceFeatureModel]


@pydantic.input(DeviceFeatureModel, description="The Feature you are trying to match")
class DeviceFeature:
    kind: str
    cpu_count: str

@pydantic.input(
    EnvironmentInputModel, description="Which environment do you want to match against?"
)
class EnvironmentInput:
    """Which environment do you want to match against?"""

    container_type: ContainerType
    features: Optional[list[DeviceFeature]]


class MatchFlavoursInputModel(BaseModel):
    """Create a new Github repository input model"""

    environment: EnvironmentInputModel | None = None
    release: strawberry.ID | None = None
    nodes: Optional[list[str]]


@pydantic.input(
    MatchFlavoursInputModel, description="Create a new Github repository input"
)
class MatchFlavoursInput:
    """Create a new Github repository input"""

    environment: EnvironmentInput | None = None
    nodes: Optional[list[NodeHash]]
    release: Optional[strawberry.ID]


class CreatePodInputModel(BaseModel):
    deployment: strawberry.ID
    local_id: strawberry.ID
    instance_id: str


@pydantic.input(CreatePodInputModel, description="Create a new Github repository input")
class CreatePodInput:
    """Create a new Github repository input"""

    deployment: strawberry.ID
    local_id: strawberry.ID
    instance_id: str


class UpdatePodInputModel(BaseModel):
    """Create a new Github repository input model"""

    pod: strawberry.ID | None
    local_id: strawberry.ID | None
    status: str
    instance_id: str



@pydantic.input(UpdatePodInputModel, description="Create a new Github repository input")
class UpdatePodInput:
    """Create a new Github repository input"""

    pod: strawberry.ID | None
    local_id: strawberry.ID | None
    status: PodStatus
    instance_id: str



class CreateDeploymentInputModel(BaseModel):
    """Create a new Github repository input model"""
    instance_id: str
    local_id: str
    flavour:  str
    last_pulled: datetime.datetime | None = None
    secret_params: Dict[str, str] | None


@pydantic.input(
    CreateDeploymentInputModel, description="Create a new Github repository input"
)
class CreateDeploymentInput:
    """Create a new Github repository input"""
    instance_id: str
    local_id: strawberry.ID
    flavour: strawberry.ID
    last_pulled: datetime.datetime | None = None
    secret_params: scalars.UntypedParams | None = None


class UpdateDeploymentInputModel(BaseModel):
    """Create a new Github repository input model"""

    deployment: strawberry.ID
    status: str


@pydantic.input(
    UpdateDeploymentInputModel, description="Create a new Github repository input"
)
class UpdateDeploymentInput:
    """Create a new Github repository input"""

    deployment: strawberry.ID
    status: PodStatus


class DumpLogsInputModel(BaseModel):
    """Create a new Github repository input model"""

    pod: str
    logs: str

@pydantic.input(DumpLogsInputModel, description="Create a new Github repository input")
class DumpLogsInput:
    """Create a new Github repository input"""

    pod: strawberry.ID
    logs: str


class DeclareBackendInputModel(BaseModel):
    """Create a new Github repository input model"""

    name: str
    kind: str

    
@pydantic.input(DeclareBackendInputModel, description="Create a new Github repository input")
class DeclareBackendInput:
    """Create a new Github repository input"""

    instance_id: str
    name: str
    kind: str
