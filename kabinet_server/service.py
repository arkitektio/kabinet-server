"""kabinet as the hub's rekuest sees it (vendored ``rekuest_service``): the service, and its HookAgent.

Two declarations, read by rekuest from one manifest and mounted by ``urls.py`` (``*service.urls``):

* the **service** says what exists: the structures kabinet hosts, the descriptors of their
  objects, and — every save and delete being announced, with no emit in the mutations — the signals
  it emits. Hub-wide; users' triggers are checked against the kinds and descriptor keys declared
  here, and the GraphQL types answer ``descriptors`` from the same declarations (``bridge.types``);
* its **agent** says what can be done: the actions rekuest runs here. Every organization has the
  agent and its own schedules, so an action does one organization's share of the work.

Nothing here loops: each run is one pass rekuest started, and a lost run is followed by the next.
"""

from django.conf import settings

from bridge import models
from embeddings import engine
from embeddings.healer import reembed_all
from rekuest_service import Descriptor, HookAgent, Service, organization_of

service = Service("kabinet", description="The hub's app, flavour and repository registry.")

# The models whose name + description are embedded (see ``embeddings.healer``).
# `Repo` and not `GithubRepo`: the vector column lives on the base table, and
# `bulk_update` only writes a model's own concrete fields.
_EMBEDDED_MODELS = (models.Definition, models.App, models.Flavour, models.Repo)


# --- Structures ---------------------------------------------------------------------------
# Most rows are upserted (``update_or_create``), which the model signals tell apart for free: a
# new row is CREATED, a refreshed one UPDATED.

ALL = ("CREATED", "UPDATED", "DELETED")
UPSERTED = ("CREATED", "UPDATED")

service.structure(
    models.App,
    "@kabinet/app",
    kinds=("CREATED",),
    organization=organization_of(),
    description="An application, known by its reverse-domain identifier.",
    signal_description="An app was registered.",
)
service.structure(
    models.Release,
    "@kabinet/release",
    kinds=UPSERTED,
    organization=organization_of("app.organization"),
    descriptors=(Descriptor("@kabinet/version", "STRING", "Its version"),),
    describe=lambda release: {"@kabinet/version": release.version},
    description="One version of an app, bundling the flavours that can be deployed for it.",
    signal_description="An app release was registered or refreshed.",
)
service.structure(
    models.Flavour,
    "@kabinet/flavour",
    kinds=UPSERTED,
    organization=organization_of("release.app.organization"),
    descriptors=(
        Descriptor("@kabinet/flavour", "STRING", "Which variant of its release it is, e.g. vanilla or cuda"),
        Descriptor("@kabinet/builder", "STRING", "The builder that produced its image"),
    ),
    describe=lambda flavour: {"@kabinet/flavour": flavour.flavour, "@kabinet/builder": flavour.builder},
    description="A runnable build of a release: one image, with the selectors and services it needs.",
    signal_description="A flavour (a runnable build of a release) was registered or refreshed.",
)
service.structure(
    models.Definition,
    "@kabinet/definition",
    kinds=UPSERTED,
    organization=organization_of(),
    descriptors=(
        Descriptor("@kabinet/kind", "STRING", "Whether it is a function or a generator"),
        Descriptor("@kabinet/scope", "STRING", "Where the data it works on lives, e.g. GLOBAL"),
        Descriptor("@kabinet/pure", "BOOL", "Whether its result may be cached"),
        Descriptor("@kabinet/idempotent", "BOOL", "Whether running it twice is the same as running it once"),
    ),
    describe=lambda d: {"@kabinet/kind": str(d.kind), "@kabinet/scope": str(d.scope), "@kabinet/pure": bool(d.pure), "@kabinet/idempotent": bool(d.idempotent)},
    description="An action definition: what an action of a flavour takes and returns, by its hash.",
    signal_description="An action definition was registered or refreshed.",
)
service.structure(
    models.Deployment,
    "@kabinet/deployment",
    kinds=ALL,
    organization=organization_of("backend.organization"),
    descriptors=(Descriptor("@kabinet/status", "STRING", "Its lifecycle status"),),
    describe=lambda deployment: {"@kabinet/status": str(deployment.status)},
    description="A flavour set to run on a backend.",
    signal_description="A deployment was created, changed status or removed.",
)
service.structure(
    models.Pod,
    "@kabinet/pod",
    kinds=ALL,
    organization=organization_of("backend.organization"),
    descriptors=(Descriptor("@kabinet/status", "STRING", "Its lifecycle status"),),
    describe=lambda pod: {"@kabinet/status": str(pod.status)},
    description="A running instance of a deployment on a backend.",
    signal_description="A pod was created, changed status or removed.",
)
service.structure(
    models.GithubRepo,
    "@kabinet/githubrepo",
    kinds=("CREATED", "DELETED"),
    organization=organization_of(),
    description="A GitHub repository scanned for deployable apps.",
    signal_description="A GitHub repository was added or removed.",
)


# --- The HookAgent ------------------------------------------------------------------------

agent = HookAgent(service)


@agent.action(
    interface="reembed_stale",
    name="Re-embed stale rows",
    description="Re-embed every row of the organization whose vector was produced by another embedding model, or by none.",
    # Scheduled only where embeddings are on; ``embeddings.sweep_interval`` is its cadence.
    default_interval=settings.EMBEDDINGS["SWEEP_INTERVAL"] if engine.enabled() else None,
)
def reembed_stale(organization: str) -> dict:
    """One pass over the organization's embedded rows, in row-locked batches (N replicas may run it at once)."""
    return {"reembedded": reembed_all(_EMBEDDED_MODELS, max_batches=50, organization=organization)}
