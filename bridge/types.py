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
    scopes: List[str]
    logo: Optional[str]
    original_logo: Optional[str]
    entrypoint: str


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

    @strawberry_django.field()
    def selectors(self, info: Info) -> List[types.Selector]:
        field_json = selectors.SelectorFieldJson(**{"selectors": self.selectors})
        return field_json.selectors





