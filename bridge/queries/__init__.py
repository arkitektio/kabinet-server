"""Queries for the bridge app."""

from .repos import github_repo
from .me import me
from .definition import definition
from .release import release
from .flavour import flavour, best_flavour

__all__ = [
    "github_repo",
    "me",
    "definition",
    "release",
    "flavour",
    "best_flavour",

]
