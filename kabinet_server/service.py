"""kabinet as a service of the hub: the models and the code behind what its contract says it hosts.

What exists here (the structures, the descriptors of their objects, the signals and their kinds)
is declared once, as data, in ``kabinet_server.contract`` (``hosts``), so that a hub knows it from the
image. This module only binds it: each structure to its model and to what computes its
descriptors, each signal to the saves and deletes that send it. A structure the contract does not
declare cannot be bound, and one it declares that nothing binds here stops the service at its
start. The GraphQL types answer ``descriptors`` from the same binding (``bridge.types``).

Hosting announces nothing by itself: a structure with no signal below is hosted silently.

That is all a service is. What can be *done* in this process is not declared here: that is an
agent's to say (``kabinet_server.hook_agent``), a different thing with its own configuration.
"""


from bridge import models
from arkitekt_service.service import Service, organization_of

from kabinet_server.contract import contract

service = Service("kabinet", hosts=contract.description.hosts, description="The hub's app, flavour and repository registry.")


# --- Structures: what kabinet hosts ---------------------------------------------------

app = service.structure(models.App, "@kabinet/app")
release = service.structure(models.Release, "@kabinet/release", describe=lambda release: {"@kabinet/version": release.version})
flavour = service.structure(
    models.Flavour,
    "@kabinet/flavour",
    describe=lambda flavour: {"@kabinet/flavour": flavour.flavour, "@kabinet/builder": flavour.builder},
)
definition = service.structure(
    models.Definition,
    "@kabinet/definition",
    describe=lambda d: {"@kabinet/kind": str(d.kind), "@kabinet/scope": str(d.scope), "@kabinet/pure": bool(d.pure), "@kabinet/idempotent": bool(d.idempotent)},
)
deployment = service.structure(models.Deployment, "@kabinet/deployment", describe=lambda deployment: {"@kabinet/status": str(deployment.status)})
pod = service.structure(models.Pod, "@kabinet/pod", describe=lambda pod: {"@kabinet/status": str(pod.status)})
githubrepo = service.structure(models.GithubRepo, "@kabinet/githubrepo")


# --- Signals: what kabinet announces ---------------------------------------------------
# Most rows are upserted (``update_or_create``), which the model signals tell apart for free: a
# new row is CREATED, a refreshed one UPDATED.

service.model_signal(app, organization=organization_of())
service.model_signal(release, organization=organization_of("app.organization"))
service.model_signal(flavour, organization=organization_of("release.app.organization"))
service.model_signal(definition, organization=organization_of())
service.model_signal(deployment, organization=organization_of("backend.organization"))
service.model_signal(pod, organization=organization_of("backend.organization"))
service.model_signal(githubrepo, organization=organization_of())
