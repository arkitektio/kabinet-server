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
    print(info)
    if info.variable_values.get("filters", {}).get("scope") is None:
        queryset = queryset.filter(**{field: info.context.request.organization})
        return queryset

    else:
        raise Exception("Custom scopes not implemented yet")


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


@strawberry_django.type(auth_models.App, description="Profile information for a user.")
class ClientApp:
    id: strawberry.ID = strawberry_django.field(description="Unique ID of the app.")
    identifier: str = strawberry_django.field(description="Name of the app.")


@strawberry_django.type(auth_models.Release, description="Profile information for a user.")
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
    description="A user of the bridge server. Maps to an authentikate user",
    filters=filters.GithubRepoFilter,
    pagination=True,
)
class GithubRepo:
    id: auto
    name: str
    repo: str
    branch: str
    user: str
    flavours: List["Flavour"]
    updated_at: datetime.datetime
    added_at: datetime.datetime
    organization: Organization

    @strawberry_django.field()
    def issue_url(self) -> str:
        return self.issue_url

    @strawberry_django.field()
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


@strawberry_django.type(models.App, description="A user of the bridge server. Maps to an authentikate user")
class App:
    id: auto
    identifier: str


@strawberry_django.type(
    models.Release,
    filters=filters.ReleaseFilter,
    pagination=True,
    description="A user of the bridge server. Maps to an authentikate user",
)
class Release:
    id: auto
    version: str
    app: App
    scopes: List[str]
    logo: Optional[str]
    original_logo: Optional[str]
    entrypoint: str
    flavours: List["Flavour"]

    @strawberry_django.field(description="Is this release deployed")
    def installed(self, info: Info) -> bool:
        return True

    @strawberry_django.field(description="Is this release deployed")
    def deployments(self, info: Info) -> List["Deployment"]:
        return models.Deployment.objects.filter(flavour__release=self).all()

    @strawberry_django.field(description="Is this release deployed")
    def description(self, info: Info) -> str:
        return "This is a basic app. That allows a few extra things"

    @strawberry_django.field(description="Is this release deployed")
    def colour(self, info: Info) -> str:
        return "#254d11"

    @strawberry_django.field(description="Is this release deployed")
    def name(self, info: Info) -> str:
        return self.app.identifier + ":" + self.version


@strawberry_django.type(
    models.Deployment,
    filters=filters.DeploymentFilter,
    pagination=True,
    description="A user of the bridge server. Maps to an authentikate user",
)
class Deployment:
    id: auto
    flavour: "Flavour"
    api_token: str
    backend: "Backend"
    local_id: strawberry.ID

    @strawberry_django.field()
    def name(self) -> str:
        return self.backend.name + "-" + self.flavour.name


@strawberry.experimental.pydantic.interface(selectors.BaseSelector, description=" A selector is a way to select a release")
class Selector:
    """A selector is a way to select a release"""

    kind: str
    required: bool


@strawberry.experimental.pydantic.type(selectors.CudaSelector, description=" A selector is a way to select a release")
class CudaSelector(Selector):
    """A selector is a way to select a release"""

    cuda_version: str | None = None
    cuda_cores: int | None = None


@strawberry.experimental.pydantic.type(selectors.RocmSelector, description=" A selector is a way to select a release")
class RocmSelector(Selector):
    """A selector is a way to select a release"""

    api_version: str | None = None
    api_thing: str | None = None


@strawberry.experimental.pydantic.type(selectors.CPUSelector, description=" A selector is a way to select a release")
class CPUSelector(Selector):
    """A selector is a way to select a release"""

    min: int | None = None
    frequency: float | None = None


@strawberry.type(description="A requirement")
class Requirement:
    key: str
    service: str
    description: str | None = None
    optional: bool = False


@strawberry_django.type(models.DockerImage, description="A docker image descriptor")
class DockerImage:
    image_string: str
    build_at: datetime.datetime


@strawberry_django.type(
    models.Flavour,
    description="A user of the bridge server. Maps to an authentikate user",
    filters=filters.FlavourFilter,
    order=filters.FlavourOrder,
    pagination=True,
)
class Flavour:
    id: auto
    name: str
    logo: Optional[str]
    image: DockerImage
    original_logo: Optional[str]
    entrypoint: CudaSelector
    release: Release
    deployments: List[Deployment]
    definitions: List["Definition"]
    manifest: scalars.UntypedParams

    @strawberry_django.field
    def repo(self, info: Info) -> GithubRepo:
        return self.repo.githubrepo

    @strawberry_django.field()
    def selectors(self, info: Info) -> List[types.Selector]:
        return self.get_selectors()

    @strawberry_django.field()
    def requirements(self) -> List[Requirement]:
        return [Requirement(**i) for i in self.requirements]

    @strawberry_django.field()
    def description(self) -> str:
        return " No description provided"


@strawberry_django.type(
    models.Collection,
    description="A user of the bridge server. Maps to an authentikate user",
)
class Collection:
    id: auto
    name: str
    description: str
    defined_at: datetime.datetime


@strawberry_django.type(
    models.Protocol,
    description="A user of the bridge server. Maps to an authentikate user",
)
class Protocol:
    id: auto
    name: str
    description: str


@strawberry_django.type(
    models.Definition,
    filters=filters.DefinitionFilter,
    order=filters.DefinitionOrder,
    pagination=True,
)
class Definition:
    id: strawberry.ID
    hash: rkscalars.ActionHash
    name: str
    kind: rkenums.ActionKind
    description: str | None
    collections: list["Collection"]
    flavours: list["Flavour"]
    scope: rkenums.ActionScope
    is_test_for: list["Definition"]
    tests: list["Definition"]
    protocols: list["Protocol"]
    defined_at: datetime.datetime

    @strawberry_django.field()
    def args(self) -> list[rtypes.ArgPort]:
        return [rmodels.ArgPortModel(**i) for i in self.args]

    @strawberry_django.field()
    def returns(self) -> list[rtypes.ReturnPort]:
        return [rmodels.ReturnPortModel(**i) for i in self.returns]


@strawberry_django.type(models.LogDump, description="The logs of a pod")
class LogDump:
    id: auto
    pod: "Pod"
    logs: str
    created_at: datetime.datetime


@strawberry_django.type(
    models.Backend,
    filters=filters.BackendFilter,
    pagination=True,
    description="A user of the bridge server. Maps to an authentikate user",
)
class Backend:
    id: auto
    user: User
    client: Client
    organization: Organization
    name: str
    kind: str
    pods: List["Pod"]
    resources: List["Resource"]
    instance_id: str

    @strawberry_django.field()
    def client_id(self) -> str:
        return self.client.client_id

    @classmethod
    def get_queryset(cls, queryset, info: Info):
        return build_prescoped_queryset(info, queryset, field="organization")


@strawberry_django.type(
    models.Resource,
    filters=filters.ResourceFilter,
    pagination=True,
    description="A resource on a backend. Resource define allocated resources on a backend. E.g a computational action",
)
class Resource:
    id: auto
    backend: Backend
    resource_id: str
    name: str
    pods: List["Pod"]
    qualifiers: scalars.UntypedParams | None


@strawberry_django.type(
    models.Pod,
    filters=filters.PodFilter,
    pagination=True,
    description="A user of the bridge server. Maps to an authentikate user",
)
class Pod:
    id: auto
    resource: Resource | None
    backend: Backend
    deployment: Deployment
    latest_log_dump: LogDump | None
    pod_id: str
    client_id: str | None
    status: enums.PodStatus

    @strawberry_django.field()
    def name(self) -> str:
        return self.backend.name + "-" + self.deployment.flavour.name + "-" + self.deployment.flavour.release.app.identifier
