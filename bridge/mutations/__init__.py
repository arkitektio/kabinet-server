"""Mutations for the bridge app."""

from .repo import scan_repo, create_github_repo, rescan_repos
from .flavour import match_flavours
from .deployment import create_deployment, update_deployment
from .pod import create_pod, update_pod, dump_logs, delete_pod
from .backend import declare_backend
from .resource import declare_resource
from .app_image import create_app_image

__all__ = [
    "scan_repo",
    "create_github_repo",
    "match_flavours",
    "create_deployment",
    "update_deployment",
    "create_pod",
    "update_pod",
    "rescan_repos",
    "dump_logs",
    "declare_backend" "delete_pod",
    "create_app_image",
]
