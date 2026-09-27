"""kabinet as the hub's rekuest sees it: the actions it offers, the signals it emits (vendored ``rekuest_service``).

Like an arkitekt ``App``: one ``Service`` declaration, mounted by ``urls.py`` (``*service.urls``),
read by rekuest from the manifest. Nothing here loops: each run is one pass rekuest started, and
a lost run is followed by the next.
"""

from django.conf import settings

from bridge import models
from embeddings import engine
from embeddings.healer import reembed_all
from rekuest_service import Service, organization_of

service = Service("kabinet", description="The hub's app, flavour and repository registry.")

# The models whose name + description are embedded (see ``embeddings.healer``).
# `Repo` and not `GithubRepo`: the vector column lives on the base table, and
# `bulk_update` only writes a model's own concrete fields.
_EMBEDDED_MODELS = (models.Definition, models.App, models.Flavour, models.Repo)


# --- Signals ------------------------------------------------------------------------------
# What kabinet announces to the hub's rekuest. Most rows are upserted (``update_or_create``),
# which the model signals tell apart for free: a new row is CREATED, a refreshed one UPDATED.

ALL = ("CREATED", "UPDATED", "DELETED")
UPSERTED = ("CREATED", "UPDATED")

service.model_signal(
    models.Release, "@kabinet/release", kinds=UPSERTED, organization=organization_of("app.organization"),
    descriptors=lambda release: {"@kabinet/version": release.version},
    descriptor_keys=("@kabinet/version",),
    description="An app release was registered or refreshed.",
)
service.model_signal(
    models.Flavour, "@kabinet/flavour", kinds=UPSERTED, organization=organization_of("release.app.organization"),
    descriptors=lambda flavour: {"@kabinet/flavour": flavour.flavour, "@kabinet/builder": flavour.builder},
    descriptor_keys=("@kabinet/flavour", "@kabinet/builder"),
    description="A flavour (a runnable build of a release) was registered or refreshed.",
)
service.model_signal(
    models.Definition, "@kabinet/definition", kinds=UPSERTED, organization=organization_of(),
    descriptors=lambda d: {"@kabinet/kind": str(d.kind), "@kabinet/scope": str(d.scope), "@kabinet/pure": bool(d.pure), "@kabinet/idempotent": bool(d.idempotent)},
    descriptor_keys=("@kabinet/kind", "@kabinet/scope", "@kabinet/pure", "@kabinet/idempotent"),
    description="An action definition was registered or refreshed.",
)
service.model_signal(
    models.Deployment, "@kabinet/deployment", kinds=ALL, organization=organization_of("backend.organization"),
    descriptors=lambda deployment: {"@kabinet/status": str(deployment.status)},
    descriptor_keys=("@kabinet/status",),
    description="A deployment was created, changed status or removed.",
)
service.model_signal(
    models.Pod, "@kabinet/pod", kinds=ALL, organization=organization_of("backend.organization"),
    descriptors=lambda pod: {"@kabinet/status": str(pod.status)},
    descriptor_keys=("@kabinet/status",),
    description="A pod was created, changed status or removed.",
)
service.model_signal(models.App, "@kabinet/app", kinds=("CREATED",), organization=organization_of(), description="An app was registered.")
service.model_signal(models.GithubRepo, "@kabinet/githubrepo", kinds=("CREATED", "DELETED"), organization=organization_of(), description="A GitHub repository was added or removed.")


@service.action(
    interface="reembed_stale",
    name="Re-embed stale rows",
    description="Re-embed every row whose vector was produced by another embedding model, or by none.",
    # Scheduled only where embeddings are on; ``embeddings.sweep_interval`` is its cadence.
    default_interval=settings.EMBEDDINGS["SWEEP_INTERVAL"] if engine.enabled() else None,
)
def reembed_stale() -> dict:
    """One pass over every embedded model, in row-locked batches (N replicas may run it at once)."""
    return {"reembedded": reembed_all(_EMBEDDED_MODELS, max_batches=50)}
