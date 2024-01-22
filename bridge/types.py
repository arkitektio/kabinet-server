import datetime
from typing import Optional

import strawberry
import strawberry.django
import strawberry_django
from django.contrib.auth import get_user_model
from strawberry import auto
from typing import List
from bridge import models, types
from bridge.repo import selectors
from kante.types import Info
from bridge.backend import get_backend
from bridge.backends import messages
from rekuest_core import enums as rkenums
from rekuest_core import scalars as rkscalars
from rekuest_core.objects import models as rmodels
from rekuest_core.objects import types as rtypes
from asgiref.sync import async_to_sync


@strawberry_django.type(get_user_model(), description="A user of the bridge server. Maps to an authentikate user")
class User:
    """ A user of the bridge server"""
    id: auto
    sub: str
    username: str
    email: str
    password: str




@strawberry_django.type(models.Repo, description="A user of the bridge server. Maps to an authentikate user")
class Repo:
    id: auto
    name: str


@strawberry_django.type(models.GithubRepo, description="A user of the bridge server. Maps to an authentikate user")
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

@strawberry_django.type(models.Release, description="A user of the bridge server. Maps to an authentikate user")
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
        return self.flavours.filter(setups__installer=info.context.request.user).first() is not None
    
    @strawberry_django.field(description="Is this release deployed")
    def setups(self, info: Info) -> List["Setup"]:
        return models.Setup.objects.filter(flavour__release=self, installer=info.context.request.user).all()

    @strawberry_django.field(description="Is this release deployed")
    def description(self, info: Info) -> str:
        return "This is a basic app. That allows a few extra things"

    @strawberry_django.field(description="Is this release deployed")
    def colour(self, info: Info) -> str:
        return "#254d11"
    
@strawberry_django.type(models.Setup, description="A user of the bridge server. Maps to an authentikate user")
class Setup:
    id: auto
    flavour: "Flavour"
    installer: User
    api_token: str



@strawberry.experimental.pydantic.type(messages.FlavourUpdate, description=" A selector is a way to select a release")
class FlavourUpdate:
    """ A selector is a way to select a release"""
    status: str
    progress: float
    id: strawberry.ID



@strawberry.experimental.pydantic.interface(selectors.BaseSelector, description=" A selector is a way to select a release")
class Selector:
    """ A selector is a way to select a release"""
    type: str
    required: bool


@strawberry.experimental.pydantic.type(selectors.CudaSelector, description=" A selector is a way to select a release")
class CudaSelector(Selector):
    """ A selector is a way to select a release"""
    compute_capability: str

@strawberry.experimental.pydantic.type(selectors.CPUSelector, description=" A selector is a way to select a release")
class CPUSelector(Selector):
    """ A selector is a way to select a release"""
    min: int
    frequency: Optional[int] = None


@strawberry_django.type(models.Flavour, description="A user of the bridge server. Maps to an authentikate user")
class Flavour:
    id: auto
    name: str
    description: str
    logo: Optional[str]
    original_logo: Optional[str]
    entrypoint: str
    image: str
    release: Release
    setups: List[Setup]

    @strawberry_django.field()
    def selectors(self, info: Info) -> List[types.Selector]:
        return self.get_selectors()
    
    @strawberry_django.field()
    def pulled(self, info: Info) -> bool:
        backend = get_backend()
        print(self.image)
        return async_to_sync(backend.ais_image_pulled)(self.image)
    
    @strawberry_django.field()
    def latest_update(self, info: Info) -> FlavourUpdate:
        return FlavourUpdate(status="Pulled", progress=1, id=self.id)



@strawberry_django.type(models.Collection, description="A user of the bridge server. Maps to an authentikate user")
class Collection:
    id: auto
    name: str
    description: str
    defined_at: datetime.datetime

@strawberry_django.type(models.Protocol, description="A user of the bridge server. Maps to an authentikate user")
class Protocol:
    id: auto
    name: str
    description: str




@strawberry_django.type(
    models.Definition, pagination=True
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




@strawberry_django.type(models.Pod, description="A user of the bridge server. Maps to an authentikate user")
class Pod:
    id: auto
    flavour: Flavour
    setup: Setup
    backend: str
    pod_id: str
    
    @strawberry.field(description="The Lifecycle of the pod")
    async def status(self, info: Info) -> str:
        backend = get_backend()
        return await backend.aget_status(self)
    
    @strawberry.field(description="The Lifecycle of the pod")
    async def logs(self, info: Info) -> str:
        backend = get_backend()
        return await backend.aget_logs(self)
    
    

    