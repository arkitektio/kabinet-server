"""Mutations for the bridge app."""

from .repo import scan_repo, create_github_repo, rescan_repos
from .deployment import create_deployment, update_deployment
from .pod import create_pod, update_pod, dump_logs, delete_pod
from .backend import declare_backend, delete_backend
from .resource import declare_resource
from .app_image import create_app_image

# `match_flavours` used to be imported and exported here from `bridge/mutations/flavour.py`.
# It was wired into neither Query nor Mutation, so nothing could call it, and its body was
# wrong in two ways regardless: it filtered `Flavour` by *its own* id using a *release* id,
# and it queried `Flavour.objects` with no organization scoping. `Query.match_flavour`
# (`bridge/queries/flavour.py`) is the implementation that is reachable and correct.

__all__ = [
    "create_app_image",
    "create_deployment",
    "create_github_repo",
    "create_pod",
    "declare_backend",
    "declare_resource",
    "delete_backend",
    "delete_pod",
    "dump_logs",
    "rescan_repos",
    "scan_repo",
    "update_deployment",
    "update_pod",
]
