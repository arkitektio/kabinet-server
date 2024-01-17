from bridge import types, models
import strawberry


async def github_repo(id: strawberry.ID) -> types.GithubRepo:
    """ Return a dask cluster by id"""
    return models.GithubRepo.objects.get(id=id)

