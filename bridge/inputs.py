from pydantic import BaseModel
from strawberry.experimental import pydantic


class ScanRepoInputModel(BaseModel):
    """Create a dask cluster input model"""
    id: str


@pydantic.input(ScanRepoInputModel, description="Create a dask cluster input")
class ScanRepoInput:
    """Create a dask cluster input"""
    id: str



class CreateGithupRepoInputModel(BaseModel):
    """ Create a new Github repository input model"""
    name: str
    user: str
    branch: str
    repo: str

@pydantic.input(CreateGithupRepoInputModel, description="Create a new Github repository input")
class CreateGithupRepoInput:
    """ Create a new Github repository input"""
    name: str
    user: str
    branch: str
    repo: str




class PullFlavourInputModel(BaseModel):
    """ Create a new Github repository input model"""
    id: str

@pydantic.input(PullFlavourInputModel, description="Create a new Github repository input")
class PullFlavourInput:
    """ Create a new Github repository input"""
    id: str



class CreateSetupInputModel(BaseModel):
    """ Create a new Github repository input model"""
    release: str
    fakts_url: str | None = "lok:80"
    fakts_token: str | None = None
    command: str | None = "arkitekt prod run"

@pydantic.input(CreateSetupInputModel, description="Create a new Github repository input")
class CreateSetupInput:
    """ Create a new Github repository input"""
    release: str
    fakts_url: str | None = None
    fakts_token: str | None = None
    command: str | None = "arkitekt prod run"

class DeploySetupInputModel(BaseModel):
    """ Create a new Github repository input model"""
    setup: str

@pydantic.input(DeploySetupInputModel, description="Create a new Github repository input")
class DeploySetupInput:
    """ Create a new Github repository input"""
    setup: str