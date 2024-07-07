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


@strawberry_django.type(
    Client, description="A user of the bridge server. Maps to an authentikate user"
)
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


@strawberry_django.type(
    models.App, description="A user of the bridge server. Maps to an authentikate user"
)
class App:
    id: auto
    identifier: str









@strawberry_django.type(
    models.Release,
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


@strawberry_django.type(
    models.Deployment,
    description="A user of the bridge server. Maps to an authentikate user",
)
class Deployment:
    id: auto
    flavour: "Flavour"
    api_token: str
    backend: "Backend"
    local_id: strawberry.ID


@strawberry.experimental.pydantic.interface(
    selectors.BaseSelector, description=" A selector is a way to select a release"
)
class Selector:
    """A selector is a way to select a release"""

    type: str
    required: bool


@strawberry.experimental.pydantic.type(
    selectors.CudaSelector, description=" A selector is a way to select a release"
)
class CudaSelector(Selector):
    """A selector is a way to select a release"""

    compute_capability: str


@strawberry.experimental.pydantic.type(
    selectors.CPUSelector, description=" A selector is a way to select a release"
)
class CPUSelector(Selector):
    """A selector is a way to select a release"""

    min: int
    frequency: Optional[int] = None


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
    original_logo: Optional[str]
    entrypoint: str
    image: str
    release: Release
    deployments: List[Deployment]
    definitions: List["Definition"]

    manifest: scalars.UntypedParams
    requirements: scalars.UntypedParams

    @strawberry_django.field()
    def selectors(self, info: Info) -> List[types.Selector]:
        return self.get_selectors()


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
    filters=filters.GithubRepoFilter,
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
    description="A user of the bridge server. Maps to an authentikate user",
)
class Backend:
    id: auto
    user: User
    client: Client
    name: str
    kind: str


@strawberry_django.type(
    models.Pod, description="A user of the bridge server. Maps to an authentikate user"
)
class Pod:
    id: auto
    backend: Backend
    deployment: Deployment
    latest_log_dump: LogDump | None
    pod_id: str
    status: enums.PodStatus
