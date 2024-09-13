import strawberry
from bridge import managers
from bridge import inputs
from bridge import models
import strawberry_django


@strawberry_django.order(models.Definition)
class DefinitionOrder:
    defined_at: strawberry.auto


@strawberry_django.filter(models.GithubRepo, description="Filter for Dask Clusters")
class GithubRepoFilter:
    """Filter for Dask Clusters"""

    ids: list[strawberry.ID] | None = None
    search: str | None = None
    pass

    def filter_search(self, queryset, search):
        return queryset.filter(name__icontains=search)

    def filter_ids(self, queryset, ids):
        return queryset.filter(id__in=ids)


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
            queryset = managers.filter_nodes_by_demands(
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


@strawberry_django.filter(models.Flavour, description="Filter for Dask Clusters")
class FlavourFilter:
    """Filter for Dask Clusters"""

    ids: list[strawberry.ID] | None = None
    search: str | None = None
    pass

    def filter_search(self, queryset, search):
        return queryset.filter(name__icontains=search)

    def filter_ids(self, queryset, ids):
        return queryset.filter(id__in=ids)


@strawberry_django.filter(models.Backend, description="Filter for Dask Clusters")
class BackendFilter:
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
    

@strawberry_django.filter(models.Pod, description="Filter for Dask Clusters")
class PodFilter:
    ids: list[strawberry.ID] | None = None
    search: str | None = None
    backend: strawberry.ID | None = None

    def filter_search(self, queryset):
        if self.search is None:
            return queryset
        return queryset.filter(backend__name=self.search)
    
    def filter_ids(self, queryset):
        if self.ids is None:
            return queryset
        return queryset.filter(id__in=self.ids)
    

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