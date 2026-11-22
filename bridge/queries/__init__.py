"""Queries for the bridge app."""

from .app import app, app_store_totals
from .backend import backend
from .definition import definition
from .deployment import deployment
from .flavour import flavour, flavour_blok
from .me import me
from .pod import my_pod_at, pod, pod_for_agent
from .release import release, release_approval
from .repos import github_repo, oci_repo, repo_blok
from .resource import resource

__all__ = [
    "app",
    "app_store_totals",
    "backend",
    "definition",
    "deployment",
    "flavour",
    "flavour_blok",
    "github_repo",
    "repo_blok",
    "me",
    "my_pod_at",
    "oci_repo",
    "pod",
    "pod_for_agent",
    "release",
    "release_approval",
    "resource",
]
