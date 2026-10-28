import strawberry
from kabinet_server.logs import QuietErrorsSchema
from strawberry_django.optimizer import DjangoOptimizerExtension
from kante.unions import unionElementOf
from bridge import types
from bridge import mutations
from bridge import subscriptions
from bridge import queries
import strawberry_django
from koherent.strawberry.extension import KoherentExtension
from authentikate.strawberry.extension import AuthentikateExtension
from authentikate.strawberry import AuthExtension, AuthSubscribeExtension
from arkitekt_service.graphql import annotate_schema
from typing import List
from rekuest_core.constants import interface_types, input_union_types
from rekuest_core.scalars import scalar_map as rscalar_map
from bridge.scalars import scalar_map as bscalar_map
from embeddings.strawberry import scalar_map as escalar_map
from bridge.repo.types import selector_types
from strawberry.schema.config import StrawberryConfig
from kabinet_server.contract import APPROVER, DEPLOYER
from kabinet_server.service import service as kabinet_service


def field(scope: str = "kabinet_read", **kwargs):
    "A field an app needs ``scope`` for (``kabinet_read``, unless it says otherwise)."
    return strawberry_django.field(extensions=[AuthExtension(scopes=[scope])], **kwargs)


def mutation(scope: str = "kabinet_deploy", roles: list[str] | None = None, **kwargs):
    """A write: an app needs ``scope`` for it, a member one of ``roles`` (``kabinet_deployer`` unless it
    says otherwise; ``kabinet_admin`` holds every role)."""
    return strawberry_django.mutation(extensions=[AuthExtension(scopes=[scope], any_role_of=roles or [DEPLOYER])], **kwargs)


def subscription(**kwargs):
    """A subscription: what it streams is read, so an app needs ``kabinet_read`` for it."""
    return strawberry.subscription(extensions=[AuthSubscribeExtension(scopes=["kabinet_read"])], **kwargs)


@strawberry.type
class Query:
    """The root query type"""

    app: types.App = field(resolver=queries.app, description="Return a single app by its ID.")
    github_repo: types.GithubRepo = field(resolver=queries.github_repo, description="Return a single tracked GitHub repository by its ID.")
    oci_repo: types.OciRepo = field(resolver=queries.oci_repo, description="Return a single imported OCI repository by its ID.")
    definition: types.Definition = field(resolver=queries.definition, description="Return a single action definition by its ID.")
    release: types.Release = field(resolver=queries.release, description="Return a single app release by its ID.")
    resource: types.Resource = field(resolver=queries.resource, description="Return a single backend resource by its ID.")
    flavour: types.Flavour = field(resolver=queries.flavour, description="Return a single flavour (a buildable variant of a release) by its ID.")
    flavour_blok: types.FlavourBlok | None = field(
        resolver=queries.flavour_blok, description="Return a single blok a flavour's app brings by its ID (`<flavour id>:<key>`), or null when there is none."
    )
    repo_blok: types.RepoBlok = field(resolver=queries.repo_blok, description="Return a single blok a repository publishes by its ID.")
    deployment: types.Deployment = field(resolver=queries.deployment, description="Return a single deployment by its ID.")
    backend: types.Backend = field(resolver=queries.backend, description="Return a single backend by its ID.")
    pod: types.Pod = field(resolver=queries.pod, description="Return a single pod by its ID.")
    pod_for_agent = field(resolver=queries.pod_for_agent, description="Return the pod that a given agent (client) is running for a deployment.")
    me: types.User = field(resolver=queries.me, description="Return the currently authenticated user.")
    flavours: List[types.Flavour] = field(description="List all flavours visible to the current organization.")
    apps: List[types.App] = field(description="List all apps visible to the current organization.")
    releases: List[types.Release] = field(description="List all app releases visible to the current organization.")
    resources: List[types.Resource] = field(description="List all backend resources visible to the current organization.")
    deployments: List[types.Deployment] = field(description="List all deployments visible to the current organization.")
    github_repos: List[types.GithubRepo] = field(description="List all tracked GitHub repositories visible to the current organization.")
    oci_repos: List[types.OciRepo] = field(description="List all imported OCI repositories visible to the current organization.")
    repo_bloks: List[types.RepoBlok] = field(description="List the bloks the tracked GitHub repositories publish on their own, visible to the current organization.")
    definitions: List[types.Definition] = field(description="List all action definitions visible to the current organization.")
    pods: List[types.Pod] = field(description="List all pods visible to the current organization.")

    backends: List[types.Backend] = field(description="List all backends visible to the current organization.")
    release_approvals: List[types.ReleaseApproval] = field(description="List all release approvals of the current organization.")
    release_approval: types.ReleaseApproval = field(resolver=queries.release_approval, description="Return a single release approval by its ID.")

    my_pod_at = field(resolver=queries.my_pod_at, description="Let a backend discover one of its own pods by local identifier.")

    # Stats
    github_repo_stats: types.GithubRepoStats = field(
        resolver=types.GithubRepoStatsResolver,
        description="Stats about github repos",
    )


@strawberry.type
class Mutation:
    """The root mutation type"""

    scan_repo: types.GithubRepo = mutation(
        scope="kabinet_repos",
        resolver=mutations.scan_repo,
        description="Scan a tracked GitHub repository for app manifests and update its flavours.",
    )
    rescan_repos: List[types.GithubRepo] = mutation(
        scope="kabinet_repos",
        resolver=mutations.rescan_repos,
        description="Rescan every tracked GitHub repository for new or updated app manifests.",
    )

    import_repo: types.OciRepo = mutation(
        scope="kabinet_repos",
        resolver=mutations.import_repo,
        description="Import an OCI repository that carries an app's releases (e.g. ghcr.io/org/app), or read an imported one again.",
    )

    create_app_image = mutation(
        scope="kabinet_repos",
        resolver=mutations.create_app_image,
        description="Register a built app image, creating its release and flavour as needed.",
    )

    create_github_repo: types.GithubRepo = mutation(
        scope="kabinet_repos",
        resolver=mutations.create_github_repo,
        description="Start tracking a new GitHub repository so it can be scanned for apps.",
    )
    create_deployment: types.Deployment = mutation(
        resolver=mutations.create_deployment,
        description="Schedule a flavour onto a backend, creating a new deployment.",
    )
    update_deployment: types.Deployment = mutation(
        resolver=mutations.update_deployment,
        description="Update the status of an existing deployment.",
    )
    create_pod: types.Pod = mutation(
        resolver=mutations.create_pod,
        description="Register a running pod for a deployment on a backend.",
    )
    update_pod: types.Pod = mutation(
        resolver=mutations.update_pod,
        description="Update the status of an existing pod.",
    )
    dump_logs: types.LogDump = mutation(
        resolver=mutations.dump_logs,
        description="Attach a captured log dump to a pod.",
    )
    declare_backend: types.Backend = mutation(
        resolver=mutations.declare_backend,
        description="Declare (register or update) a backend for the current client.",
    )
    declare_resource: types.Resource = mutation(
        resolver=mutations.declare_resource,
        description="Declare (register or update) a resource on one of your backends.",
    )

    delete_pod: strawberry.ID = mutation(
        resolver=mutations.delete_pod,
        description="Delete a pod and return its ID.",
    )
    delete_backend = mutation(
        resolver=mutations.delete_backend,
        description="Delete a backend and return its ID.",
    )
    approve_release: types.ReleaseApproval = mutation(
        scope="kabinet_approve",
        roles=[APPROVER],
        resolver=mutations.approve_release,
        description="Record a standing approval of a release (backed by a lok mandate) so deployers may install it.",
    )
    revoke_approval: types.ReleaseApproval = mutation(
        scope="kabinet_approve",
        roles=[APPROVER],
        resolver=mutations.revoke_approval,
        description="Withdraw a release approval.",
    )


@strawberry.type
class Subscription:
    """The root subscription type"""

    # Both fields used to be declared as `messages.PodUpdateMessage` while the resolvers
    # built `PodEvent`, a type that was in no schema at all -- so even once the resolvers
    # could stream, nothing they produced would serialize. `PodUpdateMessage` was never
    # constructed anywhere and is gone; `PodEvent` is the shape the publisher actually
    # has, since a delete leaves nothing but an ID behind.
    pod: subscriptions.PodEvent = subscription(
        resolver=subscriptions.pod,
        description="Subscribe to lifecycle events for a single pod.",
    )
    pods: subscriptions.PodEvent = subscription(
        resolver=subscriptions.pods,
        description="Subscribe to lifecycle events for every pod visible to the current organization.",
    )


class Schema(QuietErrorsSchema, strawberry.Schema):
    """strawberry.Schema, logging expected resolver errors as one line and bugs with a traceback (see logs.py)."""


schema = Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
    schema_directives=[unionElementOf],
    extensions=[DjangoOptimizerExtension, AuthentikateExtension, KoherentExtension],
    types=[
        types.Selector,
        types.CudaSelector,
        types.CPUSelector,
        types.RocmSelector,
        types.RAMSelector,
        types.LabelSelector,
        types.OneApiSelector,
    ]
    + interface_types
    + input_union_types
    + selector_types,
    config=StrawberryConfig(scalar_map={**rscalar_map, **bscalar_map, **escalar_map}),
)
annotate_schema(schema, kabinet_service)
