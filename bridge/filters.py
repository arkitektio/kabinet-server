import strawberry
from bridge import managers
from bridge import inputs
from bridge import models
import strawberry_django
from kante.types import Info
from django.db.models import QuerySet, Count


@strawberry_django.order(models.Definition)
class DefinitionOrder:
    defined_at: strawberry.auto


@strawberry_django.filter(models.GithubRepo, description="Filter for Dask Clusters")
class GithubRepoFilter:
    """Filter for Dask Clusters"""

    ids: list[strawberry.ID] | None = None
    search: str | None = None
    repo: str | None = None
    user: str | None = None
    branch: str | None = None
    pass

    def filter_repo(self, queryset, info):
        if self.repo is None:
            return queryset
        return queryset.filter(repo__icontains=self.repo)
    
    def filter_user(self, queryset, info):
        if self.user is None:
            return queryset
        return queryset.filter(user__icontains=self.user)
    
    def filter_branch(self, queryset, info):
        if self.branch is None:
            return queryset
        return queryset.filter(branch__icontains=self.branch)
    
    
    def filter_search(self, queryset, info):
        return queryset.filter(name__icontains=self.search) if self.search else queryset

    def filter_ids(self, queryset, info):
        if self.ids is None:
            return queryset
        return queryset.filter(id__in=self.ids)


@strawberry_django.filter(models.Definition, description="Filter for Dask Clusters")
class DefinitionFilter:
    """Filter for Dask Clusters"""

    ids: list[strawberry.ID] | None = None
    search: str | None = None
    demands: list[inputs.PortDemandInput] | None

    def filter_demands(self, queryset, info):
        print("filter_demands")

        if self.demands is None:
            return queryset

        for ports_demand in self.demands:
            queryset = managers.filter_actions_by_demands(
                queryset,
                ports_demand.matches,
                type=ports_demand.kind,
                force_length=ports_demand.force_length,
                force_non_nullable_length=ports_demand.force_non_nullable_length,
            )

        return queryset

    def filter_search(self, queryset, info):
        if self.search is None:
            return queryset

        return queryset.filter(name__icontains=self.search)

    def filter_ids(self, queryset, info):
        if self.ids is None:
            return queryset
        return queryset.filter(id__in=self.ids)


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


@strawberry_django.filter(models.Flavour, description="Filter for Dask Clusters")
class FlavourFilter:
    """Filter for Dask Clusters"""

    ids: list[strawberry.ID] | None
    search: str | None
    has_definitions: list[strawberry.ID] | None

    def filter_has_definitions(self, queryset, info):
        if self.has_definitions is None:
            return queryset
        return queryset.filter(definitions__in=self.has_definitions)

    def filter_search(self, queryset, info):
        if self.search is None:
            return queryset
        return queryset.filter(name__icontains=self.search)

    def filter_ids(self, queryset, info):
        if self.ids is None:
            return queryset
        return queryset.filter(id__in=self.ids)


@strawberry_django.filter(models.Resource, description="Filter for Resources")
class ResourceFilter:
    ids: list[strawberry.ID] | None = None
    search: str | None = None

    def filter_search(self, queryset, info):
        if self.search is None:
            return queryset
        return queryset.filter(name__icontains=self.search)

    def filter_ids(self, queryset, info):
        if self.ids is None:
            return queryset
        return queryset.filter(id__in=self.ids)


@strawberry_django.filter(models.Backend, description="Filter for Resources")
class BackendFilter:
    ids: list[strawberry.ID] | None = None
    search: str | None = None

    def filter_search(self, queryset, info):
        if self.search is None:
            return queryset
        return queryset.filter(name__icontains=self.search)

    def filter_ids(self, queryset, info):
        if self.ids is None:
            return queryset
        return queryset.filter(id__in=self.ids)


@strawberry_django.filter(models.Pod, description="Filter for Dask Clusters")
class PodFilter:
    ids: list[strawberry.ID] | None = None
    search: str | None = None
    backend: strawberry.ID | None = None

    def filter_search(self, queryset, info):
        if self.search is None:
            return queryset
        return queryset.filter(backend__name=self.search)

    def filter_ids(self, queryset, info):
        if self.ids is None:
            return queryset
        return queryset.filter(id__in=self.ids)

    def filter_backend(self, queryset, info):
        if self.backend is None:
            return queryset
        return queryset.filter(backend__id=self.backend)


@strawberry_django.filter(models.Deployment, description="Filter for Dask Clusters")
class DeploymentFilter:
    ids: list[strawberry.ID] | None = None
    search: str | None = None

    def filter_search(self, queryset):
        if self.search is None:
            return queryset
        return queryset.filter(name__icontains=self.search)

    def filter_ids(self, queryset):
        if self.ids is None:
            return queryset
        return queryset.filter(id__in=self.ids)


@strawberry_django.filter(models.Release, description="Filter for Dask Clusters")
class ReleaseFilter:
    ids: list[strawberry.ID] | None = None
    search: str | None = None

    def filter_search(self, queryset):
        if self.search is None:
            return queryset
        return queryset.filter(name__icontains=self.search)

    def filter_ids(self, queryset):
        if self.ids is None:
            return queryset
        return queryset.filter(id__in=self.ids)
