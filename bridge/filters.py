import strawberry


@strawberry.input(description="Filter for Dask Clusters")
class GithubRepoFilter:
    """Filter for Dask Clusters"""

    ids: list[strawberry.ID] | None = None
    search: str | None = None
    pass

    def filter_search(self, queryset, search):
        return queryset.filter(name__icontains=search)

    def filter_ids(self, queryset, ids):
        return queryset.filter(id__in=ids)


@strawberry.input(description="Filter for Dask Clusters")
class DefinitionFilter:
    """Filter for Dask Clusters"""

    ids: list[strawberry.ID] | None = None
    search: str | None = None
    pass

    def filter_search(self, queryset, search):
        return queryset.filter(name__icontains=search)

    def filter_ids(self, queryset, ids):
        return queryset.filter(id__in=ids)


@strawberry.input(description="Filter for Dask Clusters")
class FlavourFilter:
    """Filter for Dask Clusters"""

    ids: list[strawberry.ID] | None = None
    search: str | None = None
    pass

    def filter_search(self, queryset, search):
        return queryset.filter(name__icontains=search)

    def filter_ids(self, queryset, ids):
        return queryset.filter(id__in=ids)
