"""Mutations for the bridge app."""
from .repo import scan_repo, create_github_repo
from .flavour import pull_flavour
from .setup import create_setup, deploy_setup

__all__ = [
    "scan_repo",
    "create_github_repo",
    "pull_flavour",
    "create_setup",
    "deploy_setup"
]
