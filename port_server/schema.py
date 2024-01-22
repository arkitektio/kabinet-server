import strawberry
from strawberry_django.optimizer import DjangoOptimizerExtension
from kante.directives import upper, replace, relation
from bridge import types
from bridge import mutations
from bridge import subscriptions
from bridge import queries
import strawberry_django
from koherent.strawberry.extension import KoherentExtension
from typing import List
from rekuest_core.constants import interface_types


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
    releases: List[types.Release] = strawberry_django.field()
    definitions: List[types.Definition] = strawberry_django.field()
    pods: List[types.Pod] = strawberry_django.field()


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
    create_setup: types.Setup = strawberry_django.mutation(
        resolver=mutations.create_setup,
        description="Create a new dask cluster on a bridge server",
    )
    deploy_setup: types.Pod = strawberry_django.mutation(
        resolver=mutations.deploy_setup,
        description="Create a new dask cluster on a bridge server",
    )
    rescan_repos: list[types.GithubRepo] = strawberry_django.mutation(
        resolver=mutations.rescan_repos,
        description="Create a new dask cluster on a bridge server",
    )

@strawberry.type
class Subscription:
    """The root subscription type"""

    flavour: types.FlavourUpdate = strawberry.subscription(
        resolver=subscriptions.flavour,
        description="Create a new dask cluster on a bridge server",
    )
    flavours: types.FlavourUpdate = strawberry.subscription(
        resolver=subscriptions.flavours,
        description="Create a new dask cluster on a bridge server",
    )


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
    directives=[upper, replace, relation],
    extensions=[DjangoOptimizerExtension, KoherentExtension],
    types=[types.Selector, types.CudaSelector, types.CPUSelector] + interface_types
)
