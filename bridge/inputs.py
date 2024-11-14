import datetime
from pydantic import BaseModel, Field
from strawberry.experimental import pydantic
from .enums import PodStatus, ContainerType
import strawberry
from rekuest_core.scalars import NodeHash
from rekuest_core import enums as renums
from typing import Dict, List, Optional
from bridge import scalars
from strawberry import LazyType
from bridge import enums


class ScanRepoInputModel(BaseModel):
    """Create a dask cluster input model"""

    id: str


@pydantic.input(ScanRepoInputModel, description="Create a dask cluster input")
class ScanRepoInput:
    """Create a dask cluster input"""

    id: str


class CreateGithubRepoInput(BaseModel):
    """Create a new Github repository input model"""

    name: str | None = None
    user: str | None = None
    branch: str | None = None
    repo: str | None = None
    identifier: str | None = None
    auto_scan: bool = True


@pydantic.input(CreateGithubRepoInput, description="Create a new Github repository input")
class CreateGithubRepoInput:
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


@pydantic.input(PullFlavourInputModel, description="Create a new Github repository input")
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


@pydantic.input(CreateSetupInputModel, description="Create a new Github repository input")
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


@pydantic.input(DeploySetupInputModel, description="Create a new Github repository input")
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


@pydantic.input(EnvironmentInputModel, description="Which environment do you want to match against?")
class EnvironmentInput:
    """Which environment do you want to match against?"""

    container_type: ContainerType
    features: Optional[list[DeviceFeature]]


class MatchFlavoursInputModel(BaseModel):
    """Create a new Github repository input model"""

    environment: EnvironmentInputModel | None = None
    release: strawberry.ID | None = None
    nodes: Optional[list[str]]


@pydantic.input(MatchFlavoursInputModel, description="Create a new Github repository input")
class MatchFlavoursInput:
    """Create a new Github repository input"""

    environment: EnvironmentInput | None = None
    nodes: Optional[list[NodeHash]]
    release: Optional[strawberry.ID]


class CreatePodInputModel(BaseModel):
    deployment: strawberry.ID
    local_id: strawberry.ID
    resource: strawberry.ID | None = None
    instance_id: str
    client_id: str | None = None


@pydantic.input(CreatePodInputModel, description="Create a new Github repository input")
class CreatePodInput:
    """Create a new Github repository input"""

    deployment: strawberry.ID
    local_id: strawberry.ID
    resource: strawberry.ID | None = None
    instance_id: str
    client_id: str | None = None


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
    flavour: str
    last_pulled: datetime.datetime | None = None
    secret_params: Dict[str, str] | None


@pydantic.input(CreateDeploymentInputModel, description="Create a new Github repository input")
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


@pydantic.input(UpdateDeploymentInputModel, description="Create a new Github repository input")
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


class QualifierInputModel(BaseModel):
    """A qualifier that describes some property of the node"""
    key: str
    value: str

class DeclareResourceInputModel(BaseModel):
    """Create a new Github repository input model"""
    backend: str
    name: str
    local_id: str
    qualifiers: Optional[List[QualifierInputModel]] = None


@pydantic.input(QualifierInputModel, description="A qualifier that describes some property of the node")
class QualifierInput:
    """A qualifier that describes some property of the node"""
    key: str
    value: str


@pydantic.input(DeclareResourceInputModel, description="Create a resource")
class DeclareResourceInput:
    """Create a new Github repository input"""
    backend: strawberry.ID
    local_id: str
    name: str | None = None
    qualifiers: list[QualifierInput] | None = None
 


@strawberry.input
class PortMatchInput:
    at: int | None = None
    key: str | None = None
    kind: renums.PortKind | None = None
    identifier: str | None = None
    nullable: bool | None = None
    children: Optional[list[LazyType["PortMatchInput", __name__]]] = None


@strawberry.input
class PortDemandInput:
    kind: enums.DemandKind
    matches: list[PortMatchInput] | None = None
    force_length: int | None = None
    force_non_nullable_length: int | None = None


@strawberry.input
class DeletePodInput:
    id: strawberry.ID