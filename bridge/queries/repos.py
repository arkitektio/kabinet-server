from bridge import types, models
from bridge.scoping import get_for_org
from kante.types import Info
import strawberry


def github_repo(info: Info, id: strawberry.ID) -> types.GithubRepo:
    """Return a tracked GitHub repository by id, scoped to the request's organization."""
    return get_for_org(models.GithubRepo, info, id=id)
