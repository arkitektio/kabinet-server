import datetime
from typing import List, Optional

import strawberry
import strawberry.django
import strawberry_django
from authentikate import models as auth_models
from bridge import enums, filters, models, scalars, types
from bridge.repo import selectors
from django.contrib.auth import get_user_model
from kante.types import Info
from rekuest_core import enums as rkenums
from rekuest_core import scalars as rkscalars
from rekuest_core.objects import models as rmodels
from rekuest_core.objects import types as rtypes
from strawberry import auto
from strawberry.experimental import pydantic
from .type_gen import create_stats_type


def build_prescoped_queryset(info, queryset, field="organization"):
    # Everything is always organization-scoped; there is no per-request scope override.
    return queryset.filter(**{field: info.context.request.organization})


def build_prescoper(field="organization"):
    def prescoper(queryset, info):
        return build_prescoped_queryset(info, queryset, field=field)

    return prescoper


@strawberry_django.type(auth_models.User, description="Represents an authenticated user.")
class User:
    sub: strawberry.ID = strawberry_django.field(description="The subject identifier of the user.")


@strawberry_django.type(auth_models.Device, description="Represents a device assigned to users within an organization.")
class Device:
    id: strawberry.ID = strawberry_django.field(description="Unique ID of the device.")
    device_id: strawberry.ID = strawberry_django.field(description="The device identifier.")


@strawberry_django.type(auth_models.App, description="A client application registered with the authentication provider.")
class ClientApp:
    id: strawberry.ID = strawberry_django.field(description="Unique ID of the app.")
    identifier: str = strawberry_django.field(description="The unique identifier of the app.")


@strawberry_django.type(auth_models.Release, description="A released version of a client application.")
class ClientRelease:
    id: strawberry.ID = strawberry_django.field(description="Unique ID of the release.")
    app: ClientApp = strawberry_django.field(description="The app this release belongs to.")
    version: str = strawberry_django.field(description="Version string of the release.")


@strawberry_django.type(auth_models.Client, pagination=True, description="Represents a registered OAuth2 client.")
class Client:
    id: strawberry.ID = strawberry_django.field(description="Unique ID of the client.")
    name: str = strawberry_django.field(description="Name of the client.")
    client_id: str = strawberry_django.field(description="OAuth2 client ID.")
    release: ClientRelease | None = strawberry_django.field(description="Release associated with the client.")
    device: Device | None = strawberry_django.field(description="Device associated with the client.")


@strawberry_django.type(auth_models.Organization, description="Represents an organization in the system.")
class Organization:
    slug: str = strawberry_django.field(description="Slug of the organization.")


@strawberry_django.type(
    models.GithubRepo,
    description="A GitHub repository tracked by Kabinet and scanned for deployable Arkitekt apps.",
    filters=filters.GithubRepoFilter,
    ordering=filters.GithubRepoOrder,
    pagination=True,
)
class GithubRepo:
    id: auto
    name: str = strawberry_django.field(description="The human-readable name of the repository.")
    repo: str = strawberry_django.field(description="The repository name on GitHub (the part after the owner).")
    branch: str = strawberry_django.field(description="The branch that is scanned for app manifests.")
    user: str = strawberry_django.field(description="The GitHub owner (user or organization) of the repository.")
    flavours: List["Flavour"] = strawberry_django.field(description="The flavours discovered by scanning this repository.")
    updated_at: datetime.datetime = strawberry_django.field(description="When this repository was last updated.")
    added_at: datetime.datetime = strawberry_django.field(description="When this repository was first added to Kabinet.")
    organization: Organization = strawberry_django.field(description="The organization that owns this repository.")

    @strawberry_django.field(description="The URL for opening a new issue against this repository on GitHub.")
    def issue_url(self) -> str:
        return self.issue_url

    @strawberry_django.field(description="The URL of this repository on GitHub.")
    def url(self) -> str:
        return f"https://github.com/{self.user}/{self.repo}"

    @classmethod
    def get_queryset(cls, queryset, info: Info):
        return build_prescoped_queryset(info, queryset, field="organization")


GithubRepoStats, GithubRepoStatsResolver = create_stats_type(
    model=models.GithubRepo,
    filters=filters.GithubRepoFilter,
    allowed_fields={
        "created_at": "created_at",
    },
    allowed_datetime_fields={"created_at": "created_at"},
    prescope=build_prescoper(field="organization"),
)


@strawberry_django.type(
    models.App,
    filters=filters.AppFilter,
    ordering=filters.AppOrder,
    pagination=True,
    description="An application, identified by a globally unique, reverse-domain identifier (e.g. live.arkitekt.app).",
)
class App:
    id: auto
    identifier: str = strawberry_django.field(description="The globally unique, reverse-domain identifier of the app.")


@strawberry_django.type(
    models.Release,
    filters=filters.ReleaseFilter,
    ordering=filters.ReleaseOrder,
    pagination=True,
    description="A specific version of an app, bundling the flavours that can be deployed for it.",
)
class Release:
    id: auto
    version: str = strawberry_django.field(description="The semantic version of this release.")
    app: App = strawberry_django.field(description="The app this release belongs to.")
    scopes: List[str] = strawberry_django.field(description="The OAuth2 scopes this release requires.")
    logo: Optional[str] = strawberry_django.field(description="The stored logo of this release.")
    original_logo: Optional[str] = strawberry_django.field(description="The original (upstream) logo URL of this release.")
    entrypoint: str = strawberry_django.field(description="The entrypoint used to start the app.")
    flavours: List["Flavour"] = strawberry_django.field(description="The flavours (buildable variants) available for this release.")

    @strawberry_django.field(description="Whether this release is currently deployed somewhere.")
    def installed(self, info: Info) -> bool:
        return True

    @strawberry_django.field(description="The deployments that run a flavour of this release.")
    def deployments(self, info: Info) -> List["Deployment"]:
        return models.Deployment.objects.filter(flavour__release=self).all()

    @strawberry_django.field(description="A human-readable description of this release.")
    def description(self, info: Info) -> str:
        return "This is a basic app. That allows a few extra things"

    @strawberry_django.field(description="A display colour for this release, as a hex string.")
    def colour(self, info: Info) -> str:
        return "#254d11"

    @strawberry_django.field(description="The display name of this release, in the form 'identifier:version'.")
    def name(self, info: Info) -> str:
        return self.app.identifier + ":" + self.version


@strawberry_django.type(
    models.Deployment,
    filters=filters.DeploymentFilter,
    ordering=filters.DeploymentOrder,
    pagination=True,
    description="A flavour scheduled to run on a particular backend.",
)
class Deployment:
    id: auto
    flavour: "Flavour" = strawberry_django.field(description="The flavour that is deployed.")
    api_token: str = strawberry_django.field(description="The API token the deployed pod uses to authenticate.")
    backend: "Backend" = strawberry_django.field(description="The backend this deployment runs on.")
    local_id: strawberry.ID = strawberry_django.field(description="The identifier of this deployment as known to the backend.")

    @strawberry_django.field(description="The display name of this deployment, combining backend and flavour names.")
    def name(self) -> str:
        return self.backend.name + "-" + self.flavour.name


@strawberry.experimental.pydantic.interface(
    selectors.BaseSelector,
    description="A selector expresses a hardware (or capability) requirement that a backend must satisfy to run a flavour.",
)
class Selector:
    """A selector expresses a hardware requirement that a backend must satisfy to run a flavour."""

    kind: str
    required: bool


@strawberry.experimental.pydantic.type(
    selectors.CudaSelector,
    description="Requires a CUDA-capable (NVIDIA) GPU on the backend.",
)
class CudaSelector(Selector):
    """Requires a CUDA-capable (NVIDIA) GPU on the backend."""

    cuda_version: str | None = None
    cuda_cores: int | None = None


@strawberry.experimental.pydantic.type(
    selectors.RocmSelector,
    description="Requires a ROCm-capable (AMD) GPU on the backend.",
)
class RocmSelector(Selector):
    """Requires a ROCm-capable (AMD) GPU on the backend."""

    api_version: str | None = None
    api_thing: str | None = None


@strawberry.experimental.pydantic.type(
    selectors.CPUSelector,
    description="Requires CPU resources on the backend.",
)
class CPUSelector(Selector):
    """Requires CPU resources on the backend."""

    min: int | None = None
    frequency: float | None = None


@strawberry.type(description="A service that a flavour requires in order to run (e.g. mikro, rekuest).")
class Requirement:
    key: str = strawberry.field(description="The key identifying this requirement within the flavour.")
    service: str = strawberry.field(description="The name of the required service.")
    description: str | None = strawberry.field(default=None, description="An optional human-readable description of the requirement.")
    optional: bool = strawberry.field(default=False, description="Whether the flavour can still run if this service is unavailable.")


@strawberry_django.type(
    models.DockerImage,
    filters=filters.DockerImageFilter,
    ordering=filters.DockerImageOrder,
    pagination=True,
    description="A reference to a built Docker image.",
)
class DockerImage:
    image_string: str = strawberry_django.field(description="The fully-qualified image reference (registry/name:tag).")
    build_at: datetime.datetime = strawberry_django.field(description="When this image was built.")


@strawberry_django.type(
    models.Flavour,
    description="A buildable variant of a release: a specific Docker image together with the selectors and requirements needed to run it.",
    filters=filters.FlavourFilter,
    ordering=filters.FlavourOrder,
    pagination=True,
)
class Flavour:
    id: auto
    name: str = strawberry_django.field(description="The name of this flavour (e.g. 'vanilla', 'cuda').")
    logo: Optional[str] = strawberry_django.field(description="The stored logo of this flavour.")
    image: DockerImage = strawberry_django.field(description="The Docker image this flavour deploys.")
    original_logo: Optional[str] = strawberry_django.field(description="The original (upstream) logo URL of this flavour.")
    release: Release = strawberry_django.field(description="The release this flavour belongs to.")
    deployments: List[Deployment] = strawberry_django.field(description="The deployments that run this flavour.")
    definitions: List["Definition"] = strawberry_django.field(description="The action definitions this flavour provides.")
    manifest: scalars.UntypedParams = strawberry_django.field(description="The raw app manifest this flavour was built from.")

    @strawberry_django.field(description="The GitHub repository this flavour was built from.")
    def repo(self, info: Info) -> GithubRepo:
        return self.repo.githubrepo

    @strawberry_django.field(description="The hardware/capability selectors a backend must satisfy to run this flavour.")
    def selectors(self, info: Info) -> List[types.Selector]:
        return self.get_selectors()

    @strawberry_django.field(description="The services this flavour requires in order to run.")
    def requirements(self) -> List[Requirement]:
        return [Requirement(**i) for i in self.requirements]

    @strawberry_django.field(description="A human-readable description of this flavour.")
    def description(self) -> str:
        return " No description provided"


@strawberry_django.type(
    models.Collection,
    filters=filters.CollectionFilter,
    ordering=filters.CollectionOrder,
    pagination=True,
    description="A named grouping of related action definitions.",
)
class Collection:
    id: auto
    name: str = strawberry_django.field(description="The name of this collection.")
    description: str = strawberry_django.field(description="A description of this collection.")
    defined_at: datetime.datetime = strawberry_django.field(description="When this collection was defined.")


@strawberry_django.type(
    models.Protocol,
    filters=filters.ProtocolFilter,
    ordering=filters.ProtocolOrder,
    pagination=True,
    description="An interface that an action definition can implement (e.g. Predicate).",
)
class Protocol:
    id: auto
    name: str = strawberry_django.field(description="The name of this protocol.")
    description: str = strawberry_django.field(description="A description of this protocol.")


@strawberry_django.type(
    models.Definition,
    filters=filters.DefinitionFilter,
    ordering=filters.DefinitionOrder,
    pagination=True,
    description="An action definition: the abstract, hashed description of an RPC task that a flavour provides.",
)
class Definition:
    id: strawberry.ID
    hash: rkscalars.ActionHash = strawberry_django.field(description="The unique hash identifying this action definition.")
    name: str = strawberry_django.field(description="The cleartext name of this action.")
    kind: rkenums.ActionKind = strawberry_django.field(description="The kind of action, e.g. a function or a generator.")
    description: str | None = strawberry_django.field(description="A human-readable description of this action.")
    collections: list["Collection"] = strawberry_django.field(description="The collections this action belongs to.")
    flavours: list["Flavour"] = strawberry_django.field(description="The flavours that provide this action.")
    scope: rkenums.ActionScope = strawberry_django.field(description="The data scope of this action (e.g. local, global or bridge).")
    is_test_for: list["Definition"] = strawberry_django.field(description="The action definitions that this definition is a test for.")
    tests: list["Definition"] = strawberry_django.field(description="The action definitions that act as tests for this definition.")
    protocols: list["Protocol"] = strawberry_django.field(description="The protocols this action implements.")
    defined_at: datetime.datetime = strawberry_django.field(description="When this action definition was first defined.")

    @strawberry_django.field(description="The input ports (arguments) of this action.")
    def args(self) -> list[rtypes.ArgPort]:
        return [rmodels.ArgPortModel(**i) for i in self.args]

    @strawberry_django.field(description="The output ports (return values) of this action.")
    def returns(self) -> list[rtypes.ReturnPort]:
        return [rmodels.ReturnPortModel(**i) for i in self.returns]


@strawberry_django.type(
    models.LogDump,
    filters=filters.LogDumpFilter,
    ordering=filters.LogDumpOrder,
    pagination=True,
    description="A captured snapshot of a pod's logs at a point in time.",
)
class LogDump:
    id: auto
    pod: "Pod" = strawberry_django.field(description="The pod these logs were captured from.")
    logs: str = strawberry_django.field(description="The captured log output.")
    created_at: datetime.datetime = strawberry_django.field(description="When these logs were captured.")


@strawberry_django.type(
    models.Backend,
    filters=filters.BackendFilter,
    ordering=filters.BackendOrder,
    pagination=True,
    description="A deployment target (agent) registered by a client that runs pods on behalf of an organization.",
)
class Backend:
    id: auto
    user: User = strawberry_django.field(description="The user that registered this backend.")
    client: Client = strawberry_django.field(description="The OAuth2 client this backend authenticates as.")
    organization: Organization = strawberry_django.field(description="The organization this backend belongs to.")
    name: str = strawberry_django.field(description="The human-readable name of this backend.")
    kind: str = strawberry_django.field(description="The kind of backend (its runtime type).")
    pods: List["Pod"] = strawberry_django.field(description="The pods currently running on this backend.")
    resources: List["Resource"] = strawberry_django.field(description="The resources declared on this backend.")

    @strawberry_django.field(description="The OAuth2 client ID of this backend.")
    def client_id(self) -> str:
        return self.client.client_id

    @classmethod
    def get_queryset(cls, queryset, info: Info):
        return build_prescoped_queryset(info, queryset, field="organization")


@strawberry_django.type(
    models.Resource,
    filters=filters.ResourceFilter,
    ordering=filters.ResourceOrder,
    pagination=True,
    description="An allocatable resource on a backend (e.g. a compute slot) that pods can be scheduled onto.",
)
class Resource:
    id: auto
    backend: Backend = strawberry_django.field(description="The backend this resource belongs to.")
    resource_id: str = strawberry_django.field(description="The identifier of this resource as known to the backend.")
    name: str = strawberry_django.field(description="The human-readable name of this resource.")
    pods: List["Pod"] = strawberry_django.field(description="The pods scheduled onto this resource.")
    qualifiers: scalars.UntypedParams | None = strawberry_django.field(description="Free-form key/value qualifiers describing this resource.")

    @classmethod
    def get_queryset(cls, queryset, info: Info):
        # Resource has no direct organization; it inherits it from its backend.
        return build_prescoped_queryset(info, queryset, field="backend__organization")


@strawberry_django.type(
    models.Pod,
    filters=filters.PodFilter,
    ordering=filters.PodOrder,
    pagination=True,
    description="A running instance of a deployment on a backend.",
)
class Pod:
    id: auto
    resource: Resource | None = strawberry_django.field(description="The resource this pod is scheduled onto, if any.")
    backend: Backend = strawberry_django.field(description="The backend this pod runs on.")
    deployment: Deployment = strawberry_django.field(description="The deployment this pod is an instance of.")
    latest_log_dump: LogDump | None = strawberry_django.field(description="The most recent log dump captured from this pod.")
    pod_id: str = strawberry_django.field(description="The identifier of this pod as known to the backend.")
    client_id: str | None = strawberry_django.field(description="The OAuth2 client ID this pod authenticates as, if any.")
    status: enums.PodStatus = strawberry_django.field(description="The current lifecycle status of this pod.")

    @strawberry_django.field(description="The display name of this pod, combining backend, flavour and app identifier.")
    def name(self) -> str:
        return self.backend.name + "-" + self.deployment.flavour.name + "-" + self.deployment.flavour.release.app.identifier

    @classmethod
    def get_queryset(cls, queryset, info: Info):
        # Pod has no direct organization; it inherits it from its backend.
        return build_prescoped_queryset(info, queryset, field="backend__organization")
