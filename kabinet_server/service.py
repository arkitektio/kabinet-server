"""kabinet as a service of the hub: what exists here (``arkitekt_service.service``).

Two separate declarations, read by rekuest from the service's manifest (``*service.urls`` in
``urls.py``) and catalogued hub-wide:

* the **structures** kabinet hosts, and the descriptors of their objects. The GraphQL types answer
  ``descriptors`` from the same declarations (``bridge.types``);
* the **signals** it emits: which saves and deletes are announced, with no emit in the mutations.
  Users' triggers are checked against the kinds and descriptor keys declared here.

Hosting announces nothing by itself: a structure with no signal below is hosted silently.

That is all a service is. What can be *done* in this process is not declared here: that is an
agent's to say (``kabinet_server.hook_agent``), a different thing with its own configuration.
"""


from bridge import models
from arkitekt_service.service import Descriptor, Service, organization_of

service = Service("kabinet", description="The hub's app, flavour and repository registry.")


# --- Structures: what kabinet hosts ---------------------------------------------------

app = service.structure(
    models.App,
    "@kabinet/app",
    description="An application, known by its reverse-domain identifier.",
)
release = service.structure(
    models.Release,
    "@kabinet/release",
    descriptors=(Descriptor("@kabinet/version", "STRING", "Its version"),),
    describe=lambda release: {"@kabinet/version": release.version},
    description="One version of an app, bundling the flavours that can be deployed for it.",
)
flavour = service.structure(
    models.Flavour,
    "@kabinet/flavour",
    descriptors=(
        Descriptor("@kabinet/flavour", "STRING", "Which variant of its release it is, e.g. vanilla or cuda"),
        Descriptor("@kabinet/builder", "STRING", "The builder that produced its image"),
    ),
    describe=lambda flavour: {"@kabinet/flavour": flavour.flavour, "@kabinet/builder": flavour.builder},
    description="A runnable build of a release: one image, with the selectors and services it needs.",
)
definition = service.structure(
    models.Definition,
    "@kabinet/definition",
    descriptors=(
        Descriptor("@kabinet/kind", "STRING", "Whether it is a function or a generator"),
        Descriptor("@kabinet/scope", "STRING", "Where the data it works on lives, e.g. GLOBAL"),
        Descriptor("@kabinet/pure", "BOOL", "Whether its result may be cached"),
        Descriptor("@kabinet/idempotent", "BOOL", "Whether running it twice is the same as running it once"),
    ),
    describe=lambda d: {"@kabinet/kind": str(d.kind), "@kabinet/scope": str(d.scope), "@kabinet/pure": bool(d.pure), "@kabinet/idempotent": bool(d.idempotent)},
    description="An action definition: what an action of a flavour takes and returns, by its hash.",
)
deployment = service.structure(
    models.Deployment,
    "@kabinet/deployment",
    descriptors=(Descriptor("@kabinet/status", "STRING", "Its lifecycle status"),),
    describe=lambda deployment: {"@kabinet/status": str(deployment.status)},
    description="A flavour set to run on a backend.",
)
pod = service.structure(
    models.Pod,
    "@kabinet/pod",
    descriptors=(Descriptor("@kabinet/status", "STRING", "Its lifecycle status"),),
    describe=lambda pod: {"@kabinet/status": str(pod.status)},
    description="A running instance of a deployment on a backend.",
)
githubrepo = service.structure(
    models.GithubRepo,
    "@kabinet/githubrepo",
    description="A GitHub repository scanned for deployable apps.",
)


# --- Signals: what kabinet announces ---------------------------------------------------
# Most rows are upserted (``update_or_create``), which the model signals tell apart for free: a
# new row is CREATED, a refreshed one UPDATED.

ALL = ("CREATED", "UPDATED", "DELETED")
UPSERTED = ("CREATED", "UPDATED")

service.model_signal(
    app,
    kinds=("CREATED",),
    organization=organization_of(),
    description="An app was registered.",
)
service.model_signal(
    release,
    kinds=UPSERTED,
    organization=organization_of("app.organization"),
    description="An app release was registered or refreshed.",
)
service.model_signal(
    flavour,
    kinds=UPSERTED,
    organization=organization_of("release.app.organization"),
    description="A flavour (a runnable build of a release) was registered or refreshed.",
)
service.model_signal(
    definition,
    kinds=UPSERTED,
    organization=organization_of(),
    description="An action definition was registered or refreshed.",
)
service.model_signal(
    deployment,
    kinds=ALL,
    organization=organization_of("backend.organization"),
    description="A deployment was created, changed status or removed.",
)
service.model_signal(
    pod,
    kinds=ALL,
    organization=organization_of("backend.organization"),
    description="A pod was created, changed status or removed.",
)
service.model_signal(
    githubrepo,
    kinds=("CREATED", "DELETED"),
    organization=organization_of(),
    description="A GitHub repository was added or removed.",
)
