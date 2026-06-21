import datetime
from pydantic import BaseModel, Field
from strawberry.experimental import pydantic
from .enums import PodStatus, ContainerType
import strawberry
from rekuest_core.scalars import ActionHash
from rekuest_core import enums as renums
from rekuest_core.inputs import types as rtypes
from rekuest_core.inputs import models as rmodels
from typing import Dict, List, Optional
from bridge import scalars
from strawberry import LazyType
from bridge import enums


class ScanRepoInputModel(BaseModel):
    """Input for scanning a tracked GitHub repository."""

    id: str = Field(description="The ID of the GitHub repository to scan.")


@pydantic.input(ScanRepoInputModel, description="Input for scanning a tracked GitHub repository for app manifests.")
class ScanRepoInput:
    """Input for scanning a tracked GitHub repository."""

    id: str


class CreateGithubRepoInputModel(BaseModel):
    """Input for tracking a new GitHub repository."""

    name: str | None = Field(default=None, description="An optional human-readable name for the repository.")
    user: str | None = Field(default=None, description="The GitHub owner (user or organization) of the repository.")
    branch: str | None = Field(default=None, description="The branch to scan for app manifests.")
    repo: str | None = Field(default=None, description="The repository name on GitHub.")
    identifier: str | None = Field(default=None, description="An optional identifier (e.g. 'user/repo') used to derive the other fields.")
    auto_scan: bool = Field(default=True, description="Whether to scan the repository immediately after adding it.")


@pydantic.input(CreateGithubRepoInputModel, description="Input for tracking a new GitHub repository.")
class CreateGithubRepoInput:
    """Input for tracking a new GitHub repository."""

    name: str | None = None
    user: str | None = None
    branch: str | None = None
    repo: str | None = None
    identifier: str | None = None
    auto_scan: bool | None = True


class PullFlavourInputModel(BaseModel):
    """Input for pulling a flavour's image."""

    id: str = Field(description="The ID of the flavour to pull.")


@pydantic.input(PullFlavourInputModel, description="Input for pulling (downloading) a flavour's Docker image.")
class PullFlavourInput:
    """Input for pulling a flavour's image."""

    id: strawberry.ID


class CreateSetupInputModel(BaseModel):
    """Input for creating a deployment setup for a release."""

    release: str = Field(description="The ID of the release to set up.")
    flavour: str | None = Field(default=None, description="An optional specific flavour to use; otherwise one is matched automatically.")
    fakts_url: str | None = Field(default="lok:80", description="The Fakts endpoint the app should connect to for configuration.")
    fakts_token: str | None = Field(default=None, description="The Fakts token the app should use to authenticate.")
    command: str | None = Field(default="arkitekt prod run", description="The command used to start the app.")
    auto_pull: bool = Field(default=True, description="Whether to pull the image as part of the setup.")


@pydantic.input(CreateSetupInputModel, description="Input for creating a deployment setup for a release.")
class CreateSetupInput:
    """Input for creating a deployment setup for a release."""

    release: strawberry.ID
    flavour: strawberry.ID | None = None
    fakts_url: str | None = None
    fakts_token: str | None = None
    command: str | None = "arkitekt prod run"
    auto_pull: bool | None = True


class DeploySetupInputModel(BaseModel):
    """Input for deploying a previously created setup."""

    setup: str = Field(description="The ID of the setup to deploy.")


@pydantic.input(DeploySetupInputModel, description="Input for deploying a previously created setup.")
class DeploySetupInput:
    """Input for deploying a previously created setup."""

    setup: strawberry.ID


class DeviceFeatureModel(BaseModel):
    kind: str = Field(description="The kind of feature (e.g. 'gpu', 'cpu').")
    cpu_count: str = Field(description="The number of CPUs the feature describes.")


class EnvironmentInputModel(BaseModel):
    container_type: ContainerType = Field(description="The container runtime available in the environment.")
    features: Optional[list[DeviceFeatureModel]] = Field(default=None, description="The hardware features available in the environment.")


@pydantic.input(DeviceFeatureModel, description="A single hardware feature of a device to match against.")
class DeviceFeature:
    kind: str
    cpu_count: str


@pydantic.input(EnvironmentInputModel, description="The target environment that flavours are matched against.")
class EnvironmentInput:
    """The target environment that flavours are matched against."""

    container_type: ContainerType
    features: Optional[list[DeviceFeature]] = None


class MatchFlavoursInputModel(BaseModel):
    """Input for matching the best flavour for a release in a given environment."""

    environment: EnvironmentInputModel | None = Field(default=None, description="The target environment to match flavours against.")
    release: strawberry.ID | None = Field(default=None, description="The release whose flavours should be matched.")
    actions: Optional[list[str]] = Field(description="The action hashes that the matched flavour must provide.")


@pydantic.input(MatchFlavoursInputModel, description="Input for matching the best flavour for a release in a given environment.")
class MatchFlavoursInput:
    """Input for matching the best flavour for a release in a given environment."""

    environment: EnvironmentInput | None = None
    actions: Optional[list[ActionHash]]
    release: Optional[strawberry.ID]


class CreatePodInputModel(BaseModel):
    deployment: strawberry.ID = Field(description="The ID of the deployment this pod is an instance of.")
    local_id: strawberry.ID = Field(description="The identifier of the pod as known to the backend.")
    resource: strawberry.ID | None = Field(default=None, description="The resource this pod is scheduled onto, if any.")
    client_id: str | None = Field(default=None, description="The OAuth2 client ID this pod authenticates as, if any.")


@pydantic.input(CreatePodInputModel, description="Input for registering a running pod for a deployment.")
class CreatePodInput:
    """Input for registering a running pod for a deployment."""

    deployment: strawberry.ID
    local_id: strawberry.ID
    resource: strawberry.ID | None = None
    client_id: str | None = None


class UpdatePodInputModel(BaseModel):
    """Input for updating a pod's status."""

    pod: strawberry.ID | None = Field(description="The ID of the pod to update; required unless 'local_id' is given.")
    local_id: strawberry.ID | None = Field(description="The backend-local identifier of the pod to update.")
    status: str = Field(description="The new status of the pod.")


@pydantic.input(UpdatePodInputModel, description="Input for updating a pod's status.")
class UpdatePodInput:
    """Input for updating a pod's status."""

    pod: strawberry.ID | None
    local_id: strawberry.ID | None
    status: PodStatus


class CreateDeploymentInputModel(BaseModel):
    """Input for creating a deployment."""

    local_id: str = Field(description="The identifier of the deployment as known to the backend.")
    flavour: str = Field(description="The ID of the flavour to deploy.")
    last_pulled: datetime.datetime | None = Field(default=None, description="When the flavour's image was last pulled, if known.")
    secret_params: Dict[str, str] | None = Field(default=None, description="Secret parameters passed to the deployment (e.g. credentials).")


@pydantic.input(CreateDeploymentInputModel, description="Input for creating a deployment of a flavour on a backend.")
class CreateDeploymentInput:
    """Input for creating a deployment."""

    local_id: strawberry.ID
    flavour: strawberry.ID
    last_pulled: datetime.datetime | None = None
    secret_params: scalars.UntypedParams | None = None


class UpdateDeploymentInputModel(BaseModel):
    """Input for updating a deployment's status."""

    deployment: strawberry.ID = Field(description="The ID of the deployment to update.")
    status: str = Field(description="The new status of the deployment.")


@pydantic.input(UpdateDeploymentInputModel, description="Input for updating a deployment's status.")
class UpdateDeploymentInput:
    """Input for updating a deployment's status."""

    deployment: strawberry.ID
    status: PodStatus


class DumpLogsInputModel(BaseModel):
    """Input for attaching a log dump to a pod."""

    pod: str = Field(description="The ID of the pod the logs belong to.")
    logs: str = Field(description="The captured log output to store.")


@pydantic.input(DumpLogsInputModel, description="Input for attaching a log dump to a pod.")
class DumpLogsInput:
    """Input for attaching a log dump to a pod."""

    pod: strawberry.ID
    logs: str


class DeclareBackendInputModel(BaseModel):
    """Input for declaring (registering) a backend."""

    name: str = Field(description="The human-readable name of the backend.")
    kind: str = Field(description="The kind of backend (its runtime type).")


@pydantic.input(DeclareBackendInputModel, description="Input for declaring (registering or updating) a backend.")
class DeclareBackendInput:
    """Input for declaring (registering) a backend."""

    name: str
    kind: str


class QualifierInputModel(BaseModel):
    """A qualifier that describes some property of the action"""

    key: str = Field(description="The key of the qualifier.")
    value: str = Field(description="The value of the qualifier.")


class DeclareResourceInputModel(BaseModel):
    """Input for declaring a resource on a backend."""

    backend: str = Field(description="The ID of the backend to declare the resource on.")
    name: Optional[str] = Field(default=None, description="An optional human-readable name for the resource.")
    local_id: str = Field(description="The identifier of the resource as known to the backend.")
    qualifiers: Optional[List[QualifierInputModel]] = Field(default=None, description="Free-form key/value qualifiers describing the resource.")


@pydantic.input(
    QualifierInputModel,
    description="A qualifier that describes some property of the action",
)
class QualifierInput:
    """A qualifier that describes some property of the action"""

    key: str
    value: str


@pydantic.input(DeclareResourceInputModel, description="Input for declaring (registering or updating) a resource on a backend.")
class DeclareResourceInput:
    """Input for declaring a resource on a backend."""

    backend: strawberry.ID
    local_id: str
    name: str | None = None
    qualifiers: list[QualifierInput] | None = None



class PortDemandInputModel(BaseModel):
    """A demand on the ports (args or returns) of an action."""

    kind: enums.DemandKind = Field(description="The kind of the demand. You can ask for args or returns")
    matches: Optional[list[rmodels.PortMatchInputModel]] = Field(default=None, description="The matches of the demand. ")
    force_length: Optional[int] = Field(default=None, description="Require that the action has a specific number of ports. This is used to identify the demand in the system.")
    force_non_nullable_length: Optional[int] = Field(default=None, description="Require that the action has a specific number of non-nullable ports. This is used to identify the demand in the system.")
    force_structure_length: Optional[int] = Field(default=None, description="Require that the action has a specific number of structure ports. This is used to identify the demand in the system.")


@pydantic.input(PortDemandInputModel, description="A demand on the ports (args or returns) of an action.")
class PortDemandInput:
    kind: enums.DemandKind
    matches: list[rtypes.PortMatchInput] | None = None
    force_length: int | None = None
    force_non_nullable_length: int | None = None
    force_structure_length: int | None = None


class DeletePodInputModel(BaseModel):
    """Input for deleting a pod."""

    id: str = Field(description="The ID of the pod to delete.")


@pydantic.input(DeletePodInputModel, description="Input for deleting a pod.")
class DeletePodInput:
    id: strawberry.ID


class ActionDemandInputModel(BaseModel):
    """The input for creating an action demand."""

    key: Optional[str] = Field(default=None, description="The key of the action. This is used to identify the action in the system.")
    hash: Optional[str] = Field(default=None, description="The hash of the action. This is used to identify the action in the system.")
    name: Optional[str] = Field(default=None, description="The name of the action. This is used to identify the action in the system.")
    description: Optional[str] = Field(default=None, description="The description of the action. This can described the action and its purpose.")
    arg_matches: Optional[list[rmodels.PortMatchInputModel]] = Field(default=None, description="The demands for the action args and returns. This is used to identify the demand in the system.")
    return_matches: Optional[list[rmodels.PortMatchInputModel]] = Field(default=None, description="The demands for the action args and returns. This is used to identify the demand in the system.")
    protocols: Optional[list[str]] = Field(default=None, description="The protocols that the action has to implement. This is used to identify the demand in the system.")
    force_arg_length: Optional[int] = Field(default=None, description="Require that the action has a specific number of args. This is used to identify the demand in the system.")
    force_return_length: Optional[int] = Field(default=None, description="Require that the action has a specific number of returns. This is used to identify the demand in the system.")


@pydantic.input(ActionDemandInputModel, description="The input for creating an action demand.")
class ActionDemandInput:
    key: str | None = None
    hash: ActionHash | None = None
    name: str | None = None
    description: str | None = None
    arg_matches: list[rtypes.PortMatchInput] | None = None
    return_matches: list[rtypes.PortMatchInput] | None = None
    protocols: list[strawberry.ID] | None = None
    force_arg_length: int | None = None
    force_return_length: int | None = None


class SchemaDemandInputModel(BaseModel):
    """The input for creating a schema (state) demand."""

    key: Optional[str] = Field(default=None, description="The key of the state. This is used to identify the state in the system.")
    hash: Optional[str] = Field(default=None, description="The hash of the state.")
    matches: Optional[list[rmodels.PortMatchInputModel]] = Field(default=None, description="The demands for the action args and returns. This is used to identify the demand in the system.")
    protocols: Optional[list[str]] = Field(default=None, description="The protocols that the action has to implement. This is used to identify the demand in the system.")


@pydantic.input(SchemaDemandInputModel, description="The input for creating a schema (state) demand.")
class SchemaDemandInput:
    key: str | None = None
    hash: ActionHash | None = None
    matches: list[rtypes.PortMatchInput] | None = None
    protocols: list[strawberry.ID] | None = None