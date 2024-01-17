import strawberry
from strawberry_django.optimizer import DjangoOptimizerExtension
from kante.directives import upper, replace, relation
from bridge import types
from bridge import mutations
from bridge import queries
import strawberry_django
from koherent.strawberry.extension import KoherentExtension
from bridge.backend import ContainerBackendExtension
from typing import List

@strawberry.type
class Query:
    """The root query type"""

    github_repo: types.GithubRepo = strawberry_django.field(
        resolver=queries.github_repo, description="Return all dask clusters"
    )
    me: types.User = strawberry_django.field(
        resolver=queries.me, description="Return the currently logged in user"
    )
    flavours: List[types.Flavour] = strawberry_django.field()


@strawberry.type
class Mutation:
    """The root mutation type"""

    scan_repo: types.GithubRepo = strawberry_django.mutation(
        resolver=mutations.scan_repo,
        description="Create a new dask cluster on a bridge server",
    )
    create_github_repo: types.GithubRepo = strawberry_django.mutation(
        resolver=mutations.create_github_repo,
        description="Create a new Github repository on a bridge server",
    )
    pull_flavour: types.Flavour = strawberry_django.mutation(
        resolver=mutations.pull_flavour,
        description="Create a new dask cluster on a bridge server",
    )


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    directives=[upper, replace, relation],
    extensions=[DjangoOptimizerExtension, KoherentExtension, ContainerBackendExtension],
    types=[types.Selector, types.CudaSelector, types.CPUSelector]
)
