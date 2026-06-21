import strawberry
from bridge import managers
from bridge import inputs
from bridge import models
import strawberry_django
from kante.types import Info
from django.db.models import Q, QuerySet


@strawberry_django.order_type(models.Definition)
class DefinitionOrder:
    defined_at: strawberry.auto


@strawberry_django.filter_type(models.GithubRepo, description="Filter for tracked GitHub repositories.")
class GithubRepoFilter:
    """Filter for tracked GitHub repositories."""

    @strawberry_django.filter_field(description="Keep only repositories whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the repository name.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}name__icontains": value})

    @strawberry_django.filter_field(description="Case-insensitive match on the GitHub repository name.")
    def repo(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}repo__icontains": value})

    @strawberry_django.filter_field(description="Case-insensitive match on the GitHub owner.")
    def user(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}user__icontains": value})

    @strawberry_django.filter_field(description="Case-insensitive match on the branch name.")
    def branch(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}branch__icontains": value})


@strawberry_django.filter_type(models.Definition, description="Filter for action definitions.")
class DefinitionFilter:
    """Filter for action definitions."""

    @strawberry_django.filter_field(description="Keep only definitions whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the action name.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}name__icontains": value})

    @strawberry_django.filter_field(
        description="Keep only definitions whose ports satisfy all of the given demands.",
    )
    def demands(self, value: list[inputs.PortDemandInput], prefix: str) -> Q:
        filtered_ids = None

        for ports_demand in value:
            new_ids = managers.get_action_ids_by_demands(
                ports_demand.matches,
                type=ports_demand.kind.value,
                force_length=ports_demand.force_length,
                force_non_nullable_length=ports_demand.force_non_nullable_length,
                force_structure_length=ports_demand.force_structure_length,
                model="bridge_definition",
            )

            if filtered_ids is None:
                filtered_ids = set(new_ids)
            else:
                filtered_ids = filtered_ids.intersection(new_ids)

        if filtered_ids is None:
            return Q()

        return Q(**{f"{prefix}id__in": filtered_ids})


@strawberry_django.order_type(models.Flavour)
class FlavourOrder:
    """Order for Flavours"""

    @strawberry_django.order_field
    def released_at(
        self,
        info: Info,
        queryset: QuerySet,
        value: strawberry_django.Ordering,  # `auto` can be used instead
        prefix: str,
    ) -> tuple[QuerySet, list[str]] | list[str]:
        ordering = value.resolve(f"{prefix}release__released_at")
        return queryset, [ordering]


@strawberry_django.filter_type(models.Flavour, description="Filter for flavours.")
class FlavourFilter:
    """Filter for flavours."""

    @strawberry_django.filter_field(description="Keep only flavours whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the flavour name.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}name__icontains": value})

    @strawberry_django.filter_field(description="Keep only flavours that provide one of the given definitions.")
    def has_definitions(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}definitions__in": value})


@strawberry_django.filter_type(models.Resource, description="Filter for resources.")
class ResourceFilter:
    @strawberry_django.filter_field(description="Keep only resources whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the resource name.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}name__icontains": value})


@strawberry_django.filter_type(models.Backend, description="Filter for backends.")
class BackendFilter:
    @strawberry_django.filter_field(description="Keep only backends whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the backend name.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}name__icontains": value})


@strawberry_django.filter_type(models.Pod, description="Filter for pods.")
class PodFilter:
    @strawberry_django.filter_field(description="Keep only pods whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Match pods by the name of their backend.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}backend__name": value})

    @strawberry_django.filter_field(description="Keep only pods running on the given backend.")
    def backend(self, value: strawberry.ID, prefix: str) -> Q:
        return Q(**{f"{prefix}backend__id": value})


@strawberry_django.filter_type(models.Deployment, description="Filter for deployments.")
class DeploymentFilter:
    @strawberry_django.filter_field(description="Keep only deployments whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the deployment name.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}name__icontains": value})


@strawberry_django.filter_type(models.Release, description="Filter for app releases.")
class ReleaseFilter:
    @strawberry_django.filter_field(description="Keep only releases whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the release version.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}version__icontains": value})


@strawberry_django.filter_type(models.App, description="Filter for apps.")
class AppFilter:
    @strawberry_django.filter_field(description="Keep only apps whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the app identifier.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}identifier__icontains": value})


@strawberry_django.filter_type(models.DockerImage, description="Filter for Docker images.")
class DockerImageFilter:
    @strawberry_django.filter_field(description="Keep only images whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the image reference.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}image_string__icontains": value})


@strawberry_django.filter_type(models.Collection, description="Filter for collections.")
class CollectionFilter:
    @strawberry_django.filter_field(description="Keep only collections whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the collection name.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}name__icontains": value})


@strawberry_django.filter_type(models.Protocol, description="Filter for protocols.")
class ProtocolFilter:
    @strawberry_django.filter_field(description="Keep only protocols whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the protocol name.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}name__icontains": value})


@strawberry_django.filter_type(models.LogDump, description="Filter for log dumps.")
class LogDumpFilter:
    @strawberry_django.filter_field(description="Keep only log dumps whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the captured log text.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}logs__icontains": value})


# ---------------------------------------------------------------------------
# Orders — one per model so every list query can be sorted.
# ---------------------------------------------------------------------------


@strawberry_django.order_type(models.GithubRepo)
class GithubRepoOrder:
    id: strawberry.auto
    name: strawberry.auto
    added_at: strawberry.auto
    updated_at: strawberry.auto


@strawberry_django.order_type(models.App)
class AppOrder:
    id: strawberry.auto
    identifier: strawberry.auto


@strawberry_django.order_type(models.Release)
class ReleaseOrder:
    id: strawberry.auto
    version: strawberry.auto
    released_at: strawberry.auto
    created_at: strawberry.auto


@strawberry_django.order_type(models.DockerImage)
class DockerImageOrder:
    id: strawberry.auto
    image_string: strawberry.auto
    build_at: strawberry.auto
    created_at: strawberry.auto


@strawberry_django.order_type(models.Collection)
class CollectionOrder:
    id: strawberry.auto
    name: strawberry.auto
    defined_at: strawberry.auto


@strawberry_django.order_type(models.Protocol)
class ProtocolOrder:
    id: strawberry.auto
    name: strawberry.auto


@strawberry_django.order_type(models.LogDump)
class LogDumpOrder:
    id: strawberry.auto
    created_at: strawberry.auto


@strawberry_django.order_type(models.Backend)
class BackendOrder:
    id: strawberry.auto
    name: strawberry.auto
    last_heartbeat: strawberry.auto


@strawberry_django.order_type(models.Resource)
class ResourceOrder:
    id: strawberry.auto
    name: strawberry.auto
    created_at: strawberry.auto


@strawberry_django.order_type(models.Pod)
class PodOrder:
    id: strawberry.auto
    status: strawberry.auto
    created_at: strawberry.auto


@strawberry_django.order_type(models.Deployment)
class DeploymentOrder:
    id: strawberry.auto
    local_id: strawberry.auto
    created_at: strawberry.auto
