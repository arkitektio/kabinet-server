"""kabinet's hook agent: the work the hub's rekuest can ask of this process (``arkitekt_service.hook``).

An agent of its own, not a part of the service declared in ``kabinet_server.service``: the service
says what exists, the agent says what can be done. Each has its own entry in the hub's
configuration (``rekuest.services`` / ``rekuest.hook_agents``) and its own endpoints (``urls.py``).

Every organization has the agent, so an action is handed the slug of the organization a run is
for and does that organization's share of the work, nothing else. Nothing is wired: whether and
when an action runs (a schedule, a trigger, by hand) is the organization's own automation.
Nothing here loops or waits: each run is one pass rekuest started.
"""

from asgiref.sync import async_to_sync

from bridge import models
from bridge.repo import oci
from embeddings.healer import reembed_all
from arkitekt_service.hook import HookAgent

agent = HookAgent("kabinet", description="kabinet's housekeeping: work on its own data.")

# The models whose name + description are embedded (see ``embeddings.healer``).
# `Repo` and not `GithubRepo`: the vector column lives on the base table, and
# `bulk_update` only writes a model's own concrete fields.
_EMBEDDED_MODELS = (models.Definition, models.App, models.Flavour, models.Repo)


@agent.action(
    interface="reembed_stale",
    name="Re-embed stale rows",
    description="Re-embed every row of the organization whose vector was produced by another embedding model, or by none.",
)
def reembed_stale(organization: str) -> dict:
    """One pass over the organization's embedded rows, in row-locked batches (N replicas may run it at once)."""
    return {"reembedded": reembed_all(_EMBEDDED_MODELS, max_batches=50, organization=organization)}


@agent.action(
    interface="rescan_sources",
    name="Read imported repositories again",
    description="Read every OCI repository the organization imported, and write the releases and channel builds published since.",
)
def rescan_sources(organization: str) -> dict:
    """One pass over the organization's imported repositories. A repository that cannot be read is counted, not fatal."""
    releases, unreadable = 0, 0
    for repo in models.OciRepo.objects.filter(organization__slug=organization):
        try:
            releases += len(async_to_sync(oci.scan)(repo).releases)
        except oci.RegistryError:
            unreadable += 1
    return {"releases": releases, "unreadable": unreadable}
