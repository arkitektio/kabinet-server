import datetime
from typing import List, Optional

import strawberry
import strawberry.django
import strawberry_django
from authentikate.models import App as Client
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


@strawberry_django.type(Client, description="A user of the bridge server. Maps to an authentikate user")
class Client:
    id: auto
    identifier: str


@strawberry_django.type(
    get_user_model(),
    description="A user of the bridge server. Maps to an authentikate user",
)
class User:
    """A user of the bridge server"""

    id: auto
    sub: str
    username: str
    email: str
    password: str


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
    compute_capability: str
    cuda_version: str
    cuda_cores: int

@strawberry.experimental.pydantic.type(selectors.RocmSelector, description=" A selector is a way to select a release")
class RocmSelector(Selector):
    """A selector is a way to select a release"""
    api_version: str
    api_thing: str


@strawberry.experimental.pydantic.type(selectors.CPUSelector, description=" A selector is a way to select a release")
class CPUSelector(Selector):
    """A selector is a way to select a release"""

    min: int
    frequency: Optional[int] = None



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
    pagination=True,
)
class Flavour:
    id: auto
    name: str
    description: str
    logo: Optional[str]
    image: DockerImage
    original_logo: Optional[str]
    entrypoint: CudaSelector
    release: Release
    deployments: List[Deployment]
    definitions: List["Definition"]

    manifest: scalars.UntypedParams

    @strawberry_django.field()
    def selectors(self, info: Info) -> List[types.Selector]:
        return self.get_selectors()
    
    @strawberry_django.field()
    def requirements(self) -> List[Requirement]:
        return [Requirement(**i) for i in self.requirements]
    


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
    hash: rkscalars.NodeHash
    name: str
    kind: rkenums.NodeKind
    description: str | None
    collections: list["Collection"]
    flavours: list["Flavour"]
    scope: rkenums.NodeScope
    is_test_for: list["Definition"]
    tests: list["Definition"]
    protocols: list["Protocol"]
    defined_at: datetime.datetime

    @strawberry_django.field()
    def args(self) -> list[rtypes.Port]:
        return [rmodels.PortModel(**i) for i in self.args]

    @strawberry_django.field()
    def returns(self) -> list[rtypes.Port]:
        return [rmodels.PortModel(**i) for i in self.returns]


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
    name: str
    kind: str
    pods: List["Pod"]
    resources: List["Resource"]
    instance_id: str

    @strawberry_django.field()
    def client_id(self) -> str:
        return self.client.client_id



@strawberry_django.type(
    models.Resource,
    filters=filters.ResourceFilter,
    pagination=True,
    description="A resource on a backend. Resource define allocated resources on a backend. E.g a computational node",
)
class Resource:
    id: auto
    backend: Backend
    resource_id: str
    name: str
    pods: List["Pod"]
    qualifiers: scalars.UntypedParams | None



@strawberry_django.type(models.Pod, filters=filters.PodFilter, pagination=True, description="A user of the bridge server. Maps to an authentikate user")
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
        return self.pod_id + "-" + self.deployment.flavour.name
