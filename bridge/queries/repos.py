from bridge import types, models
from bridge.scoping import get_for_org
from kante.types import Info
import strawberry


def github_repo(info: Info, id: strawberry.ID) -> types.GithubRepo:
    """Return a tracked GitHub repository by id, scoped to the request's organization."""
    return get_for_org(models.GithubRepo, info, id=id)


def oci_repo(info: Info, id: strawberry.ID) -> types.OciRepo:
    """Return an imported OCI repository by id, scoped to the request's organization."""
    return get_for_org(models.OciRepo, info, id=id)


def repo_blok(info: Info, id: strawberry.ID) -> types.RepoBlok:
    """Return a blok a repository publishes by id, scoped to the request's organization."""
    return get_for_org(models.RepoBlok, info, id=id)
