"""kabinet as a service of the hub: the models and the code behind what its contract says it hosts.

What exists here (the structures, the descriptors of their objects, the signals and their kinds)
is declared once, as data, in ``kabinet_server.contract`` (``hosts``), so that a hub knows it from the
image. This module only binds it: each structure to its model and to what computes its
descriptors, each signal to the saves and deletes that send it. A structure the contract does not
declare cannot be bound, and one it declares that nothing binds here stops the service at its
start. Each described row stores its descriptors on every save (``stored_descriptors``): the
GraphQL types answer ``descriptors`` from there, and a filter's ``requires`` reads it in SQL.

Hosting announces nothing by itself: a structure with no signal below is hosted silently.

That is all a service is. What can be *done* in this process is not declared here: that is an
agent's to say (``kabinet_server.hook_agent``), a different thing with its own configuration.
"""

from arkitekt_service.collaborations import items as collaboration_items
from arkitekt_service.service import Service, organization_of
from django.db.models import Model, Q
from django.db.models.signals import m2m_changed, post_save

from bridge import models
from kabinet_server import descriptors
from kabinet_server.contract import contract

service = Service(
    "kabinet",
    hosts=contract.description.hosts,
    description="The hub's app, flavour and repository registry.",
)


# --- Collaborations: what a guest of the organization may be shown -------------------------
# An app is what is put in a collaboration: its releases and their flavours are part of it and come
# with it, live; what else they need to be seen (each flavour's image and the actions it provides)
# is brought along. An action definition and a repository (with the bloks it publishes) can be put
# in by themselves.
#
# Never shared: where the organization runs things (deployments, pods, and the backends, resources
# and logs they hang on), who approved what to run under its mandate (release approvals), and its
# catalogs, configuration that reading also refreshes. They cannot be put in by hand
# (``SHAREABLE``), a workflow share never puts them in (``created_under`` matches nothing), and
# they are part of nothing that is shared (``not_part_of``).


def _never(root_task_id: str) -> Q:
    """No workflow's objects of a structure that is never shared."""
    return Q(pk__in=[])


def _app_needs(app: models.App) -> list[Model | None]:
    """The image each flavour of the app deploys, and the actions each provides."""
    flavours = models.Flavour.objects.filter(release__app=app)
    return [
        *models.DockerImage.objects.filter(flavours__in=flavours).distinct(),
        *models.Definition.objects.filter(flavours__in=flavours).distinct(),
    ]


# --- Structures: what kabinet hosts ---------------------------------------------------
# What a workflow (a root task) created is read off ``created_through``, stamped when a repository
# or an app image is imported under a provenance token.

app = service.structure(models.App, "@kabinet/app", depends=_app_needs)
release = service.structure(
    models.Release, "@kabinet/release", describe=descriptors.release_descriptors
)
flavour = service.structure(
    models.Flavour, "@kabinet/flavour", describe=descriptors.flavour_descriptors
)
definition = service.structure(
    models.Definition,
    "@kabinet/definition",
    describe=descriptors.definition_descriptors,
)
deployment = service.structure(
    models.Deployment,
    "@kabinet/deployment",
    describe=descriptors.placement_descriptors,
    created_under=_never,
)
pod = service.structure(
    models.Pod,
    "@kabinet/pod",
    describe=descriptors.placement_descriptors,
    created_under=_never,
)
githubrepo = service.structure(models.GithubRepo, "@kabinet/githubrepo")
catalog = service.structure(models.Catalog, "@kabinet/catalog", created_under=_never)
catalogentry = service.structure(
    models.CatalogEntry, "@kabinet/catalogentry", created_under=_never
)

#: What a full member may put in a collaboration by hand.
SHAREABLE: frozenset[type[Model]] = frozenset(
    {models.App, models.Release, models.Flavour, models.Definition, models.GithubRepo}
)

# A flavour is its release's, not part of the image it deploys (an image may be any flavour's);
# a deployment runs a flavour but is the organization's; an approval is its release's record of
# who let it run, never a guest's to read.
service.not_part_of(models.Flavour, "image")
service.not_part_of(models.Deployment, "flavour")
service.not_part_of(models.ReleaseApproval, "release")


def _flavour_saved(
    sender: type[models.Flavour],
    instance: models.Flavour,
    raw: bool = False,
    **_: object,
) -> None:
    """A flavour imported into an app in a collaboration brings its image into it."""
    if not raw:
        collaboration_items.refresh(instance.release.app)


def _definitions_changed(
    sender: type[Model],
    instance: models.Definition | models.Flavour,
    action: str,
    reverse: bool = False,
    pk_set: set[int] | None = None,
    **_: object,
) -> None:
    """An action provided by a flavour of an app in a collaboration comes into it."""
    if action != "post_add":
        return
    flavours = (
        models.Flavour.objects.filter(pk=instance.pk)
        if reverse
        else models.Flavour.objects.filter(pk__in=pk_set or ())
    )
    for app in models.App.objects.filter(releases__flavours__in=flavours).distinct():
        collaboration_items.refresh(app)


post_save.connect(
    _flavour_saved, sender=models.Flavour, dispatch_uid="kabinet-collaborations-flavour"
)
m2m_changed.connect(
    _definitions_changed,
    sender=models.Definition.flavours.through,
    dispatch_uid="kabinet-collaborations-definitions",
)


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
service.model_signal(catalog, organization=organization_of())
service.model_signal(catalogentry, organization=organization_of("catalog.organization"))
