"""Queries for the bridge app."""

from .repos import github_repo
from .me import me

__all__ = [
    "github_repo",
    "me",
]
