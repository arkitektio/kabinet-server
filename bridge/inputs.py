from pydantic import BaseModel
from strawberry.experimental import pydantic
from .enums import PodStatus, ContainerType
import strawberry


class ScanRepoInputModel(BaseModel):
    """Create a dask cluster input model"""

    id: str


@pydantic.input(ScanRepoInputModel, description="Create a dask cluster input")
class ScanRepoInput:
    """Create a dask cluster input"""

    id: str


class CreateGithupRepoInputModel(BaseModel):
    """Create a new Github repository input model"""

    name: str
    user: str
    branch: str
    repo: str
    auto_scan: bool = True


@pydantic.input(
    CreateGithupRepoInputModel, description="Create a new Github repository input"
)
class CreateGithupRepoInput:
    """Create a new Github repository input"""

    name: str
    user: str
    branch: str
    repo: str
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


class EnvironmentInputModel(BaseModel):
    container_type: ContainerType


@pydantic.input(
    EnvironmentInputModel, description="Which environment do you want to match against?"
)
class EnvironmentInput:
    """Which environment do you want to match against?"""

    container_type: ContainerType


class MatchFlavoursInputModel(BaseModel):
    """Create a new Github repository input model"""

    environment: EnvironmentInputModel
    release: strawberry.ID | None = None


@pydantic.input(
    MatchFlavoursInputModel, description="Create a new Github repository input"
)
class MatchFlavoursInput:
    """Create a new Github repository input"""

    environment: strawberry.ID
    release: strawberry.ID | None = None


class CreatePodInputModel(BaseModel):
    deployment: strawberry.ID
    instance_id: str


@pydantic.input(CreatePodInputModel, description="Create a new Github repository input")
class CreatePodInput:
    """Create a new Github repository input"""

    deployment: strawberry.ID
    instance_id: str


class UpdatePodInputModel(BaseModel):
    """Create a new Github repository input model"""

    pod: strawberry.ID
    status: str


@pydantic.input(UpdatePodInputModel, description="Create a new Github repository input")
class UpdatePodInput:
    """Create a new Github repository input"""

    pod: strawberry.ID
    status: PodStatus


class CreateDeploymentInputModel(BaseModel):
    """Create a new Github repository input model"""
    instance_id: strawberry.ID
    flavour: strawberry.ID
    pulled: bool = False


@pydantic.input(
    CreateDeploymentInputModel, description="Create a new Github repository input"
)
class CreateDeploymentInput:
    """Create a new Github repository input"""
    instance_id: strawberry.ID
    flavour: strawberry.ID
    pulled: bool | None = False


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
