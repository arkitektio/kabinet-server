"""Queries for the bridge app."""

from .repos import github_repo
from .me import me
from .definition import definition
from .release import release
from .flavour import flavour, match_flavour
from .pod import pod, pod_for_agent
from .deployment import deployment
from .backend import backend
from .resource import resource

__all__ = [
    "github_repo",
    "me",
    "definition",
    "release",
    "flavour",
    "match_flavour",
    "pod",
    "pod_for_agent",
    "deployment",
    "backend",
]
