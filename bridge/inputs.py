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