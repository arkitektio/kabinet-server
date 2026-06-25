import strawberry
from strawberry_django.optimizer import DjangoOptimizerExtension
from bridge.directives import unionElementOf
from bridge import types
from bridge import mutations
from bridge import subscriptions
from bridge import queries
from bridge import messages
import strawberry_django
from koherent.strawberry.extension import KoherentExtension
from authentikate.strawberry.extension import AuthentikateExtension
from typing import List
from rekuest_core.constants import interface_types
from rekuest_core.scalars import scalar_map as rscalar_map
from bridge.scalars import scalar_map as bscalar_map
from bridge.repo.types import selector_types
from strawberry.schema.config import StrawberryConfig


@strawberry.type
class Query:
    """The root query type"""

    github_repo: types.GithubRepo = strawberry_django.field(resolver=queries.github_repo, description="Return a single tracked GitHub repository by its ID.")
    definition: types.Definition = strawberry_django.field(resolver=queries.definition, description="Return a single action definition by its ID.")
    release: types.Release = strawberry_django.field(resolver=queries.release, description="Return a single app release by its ID.")
    resource: types.Resource = strawberry_django.field(resolver=queries.resource, description="Return a single backend resource by its ID.")
    flavour: types.Flavour = strawberry_django.field(resolver=queries.flavour, description="Return a single flavour (a buildable variant of a release) by its ID.")
    deployment: types.Deployment = strawberry_django.field(resolver=queries.deployment, description="Return a single deployment by its ID.")
    backend: types.Backend = strawberry_django.field(resolver=queries.backend, description="Return a single backend by its ID.")
    pod: types.Pod = strawberry_django.field(resolver=queries.pod, description="Return a single pod by its ID.")
    pod_for_agent = strawberry_django.field(resolver=queries.pod_for_agent, description="Return the pod that a given agent (client) is running for a deployment.")
    me: types.User = strawberry_django.field(resolver=queries.me, description="Return the currently authenticated user.")
    match_flavour: types.Flavour = strawberry_django.field(
        resolver=queries.match_flavour,
        description="Return the flavour that best matches the requested release, actions and target environment.",
    )
    flavours: List[types.Flavour] = strawberry_django.field(description="List all flavours visible to the current organization.")
    releases: List[types.Release] = strawberry_django.field(description="List all app releases visible to the current organization.")
    resources: List[types.Resource] = strawberry_django.field(description="List all backend resources visible to the current organization.")
    deployments: List[types.Deployment] = strawberry_django.field(description="List all deployments visible to the current organization.")
    github_repos: List[types.GithubRepo] = strawberry_django.field(description="List all tracked GitHub repositories visible to the current organization.")
    definitions: List[types.Definition] = strawberry_django.field(description="List all action definitions visible to the current organization.")
    pods: List[types.Pod] = strawberry_django.field(description="List all pods visible to the current organization.")

    backends: List[types.Backend] = strawberry_django.field(description="List all backends visible to the current organization.")

    my_pod_at = strawberry_django.field(resolver=queries.my_pod_at, description="Let a backend discover one of its own pods by local identifier.")

    # Stats
    github_repo_stats: types.GithubRepoStats = strawberry_django.field(
        resolver=types.GithubRepoStatsResolver,
        description="Stats about github repos",
    )


@strawberry.type
class Mutation:
    """The root mutation type"""

    scan_repo: types.GithubRepo = strawberry_django.mutation(
        resolver=mutations.scan_repo,
        description="Scan a tracked GitHub repository for app manifests and update its flavours.",
    )
    rescan_repos: List[types.GithubRepo] = strawberry_django.mutation(
        resolver=mutations.rescan_repos,
        description="Rescan every tracked GitHub repository for new or updated app manifests.",
    )

    create_app_image = strawberry_django.mutation(
        resolver=mutations.create_app_image,
        description="Register a built app image, creating its release and flavour as needed.",
    )

    create_github_repo: types.GithubRepo = strawberry_django.mutation(
        resolver=mutations.create_github_repo,
        description="Start tracking a new GitHub repository so it can be scanned for apps.",
    )
    create_deployment: types.Deployment = strawberry_django.mutation(
        resolver=mutations.create_deployment,
        description="Schedule a flavour onto a backend, creating a new deployment.",
    )
    update_deployment: types.Deployment = strawberry_django.mutation(
        resolver=mutations.update_deployment,
        description="Update the status of an existing deployment.",
    )
    create_pod: types.Pod = strawberry_django.mutation(
        resolver=mutations.create_pod,
        description="Register a running pod for a deployment on a backend.",
    )
    update_pod: types.Pod = strawberry_django.mutation(
        resolver=mutations.update_pod,
        description="Update the status of an existing pod.",
    )
    dump_logs: types.LogDump = strawberry_django.mutation(
        resolver=mutations.dump_logs,
        description="Attach a captured log dump to a pod.",
    )
    declare_backend: types.Backend = strawberry_django.mutation(
        resolver=mutations.declare_backend,
        description="Declare (register or update) a backend for the current client.",
    )
    declare_resource: types.Resource = strawberry_django.mutation(
        resolver=mutations.declare_resource,
        description="Declare (register or update) a resource on one of your backends.",
    )

    delete_pod: strawberry.ID = strawberry_django.mutation(
        resolver=mutations.delete_pod,
        description="Delete a pod and return its ID.",
    )
    delete_backend = strawberry_django.mutation(
        resolver=mutations.delete_backend,
        description="Delete a backend and return its ID.",
    )


@strawberry.type
class Subscription:
    """The root subscription type"""

    pod: messages.PodUpdateMessage = strawberry.subscription(
        resolver=subscriptions.pod,
        description="Subscribe to status updates for a single pod.",
    )
    pods: messages.PodUpdateMessage = strawberry.subscription(
        resolver=subscriptions.pods,
        description="Subscribe to status updates for all pods visible to the current organization.",
    )


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
    schema_directives=[unionElementOf],
    extensions=[DjangoOptimizerExtension, AuthentikateExtension, KoherentExtension],
    types=[types.Selector, types.CudaSelector, types.CPUSelector, types.RocmSelector] + interface_types + selector_types,
    config=StrawberryConfig(scalar_map={**rscalar_map, **bscalar_map}),
)
