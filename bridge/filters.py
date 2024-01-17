import strawberry


@strawberry.input(description="Filter for Dask Clusters")
class ClusterFilter:
    """Filter for Dask Clusters"""
    ids: list[strawberry.ID] | None = None
    search: str | None = None
    pass
