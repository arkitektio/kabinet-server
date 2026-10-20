"""What this image answers a hub's installer: ``arkitekt-service <verb>`` (see ``arkitekt_service.contract``).

The installer knows the hub; how this release spells its config is written here, with the
settings it is read by. A key renamed in ``configuration.py`` is renamed in :func:`render` in
the same commit, and no installer has to learn of it.
"""

from __future__ import annotations

from arkitekt_service.contract import JSON, Contract, Description, Descriptor, Facts, Hosts, Job, Needs, Offers, Scope, Signal, Start, Structure, blocks

from kabinet_server.configuration import Settings

#: What a token may be allowed to do here: defined at the coordination server when the hub enrols.
SCOPES = [
    Scope(key="kabinet_add_repo", description="Add repositories to the database"),
    Scope(key="kabinet_deploy", description="Deploy containers"),
    Scope(key="kabinet_read", description="Read container definitions"),
    Scope(key="read", description="Generic read access"),
    Scope(key="write", description="Generic write access"),
]

#: The roles a member of an organization can hold here.
ROLES = [
    Scope(key="admin", description="Full administrative access"),
    Scope(key="deployer", description="Can deploy containers"),
    Scope(key="user", description="Standard user access"),
    Scope(key="viewer", description="Read-only access"),
]

#: What a deployment and a pod are placed by: one pair of keys for both, so one `requires` asks both.
_STATUS = Descriptor(key="@kabinet/status", type="STRING", description="Its lifecycle status as its backend last reported it, e.g. PENDING, RUNNING, STOPPED or FAILED")
_BACKEND_KIND = Descriptor(key="@kabinet/backend_kind", type="STRING", description="The kind of deployer backend it runs on, as the backend declared it (e.g. docker); unknown until it does")

RELEASE_DESCRIPTORS = [
    Descriptor(key="@kabinet/version", type="STRING", description="Its version"),
    Descriptor(key="@kabinet/channel", type="STRING", description="The channel it is the latest build of (e.g. main): empty for a release proper, which never changes"),
]
#: Read off the selectors a backend must satisfy (``required``); a preference is no minimum.
FLAVOUR_DESCRIPTORS = [
    Descriptor(key="@kabinet/flavour_name", type="STRING", description="Which variant of its release it is, e.g. vanilla or cuda"),
    Descriptor(key="@kabinet/selector_kinds", type="LIST", description="The kinds of hardware selector it states, required or preferred: cpu, ram, cuda, rocm, oneapi, label"),
    Descriptor(
        key="@kabinet/gpu",
        type="STRING",
        description="The GPU accelerator a backend must have to run it: cuda, rocm or oneapi; none when it requires none, multiple when it requires more than one vendor's",
    ),
    Descriptor(key="@kabinet/arch", type="LIST", description="The CPU architectures it requires (e.g. amd64, arm64): empty when any will do"),
    Descriptor(key="@kabinet/min_ram_mb", type="INT", description="The system memory it requires, in MB: 0 when it states none"),
    Descriptor(key="@kabinet/min_vram_mb", type="INT", description="The GPU memory it requires of a CUDA device, in MB: 0 when it states none"),
]
DEFINITION_DESCRIPTORS = [
    Descriptor(key="@kabinet/kind", type="STRING", description="Whether the action is a function or a generator"),
    Descriptor(key="@kabinet/pure", type="BOOL", description="Whether it is pure, so its result may be cached"),
    Descriptor(key="@kabinet/idempotent", type="BOOL", description="Whether running it twice is the same as running it once"),
    Descriptor(key="@kabinet/n_args", type="INT", description="How many arguments it takes: 0 for an action a schedule can start"),
    Descriptor(key="@kabinet/n_returns", type="INT", description="How many values it returns"),
]
PLACEMENT_DESCRIPTORS = [_STATUS, _BACKEND_KIND]


def _keys(descriptors: list[Descriptor]) -> list[str]:
    return [descriptor.key for descriptor in descriptors]


#: What exists on a hub because this service is there: said here, as data, so the hub knows it from
#: the image. ``service.py`` binds each of these to its model and refuses anything not said here.
HOSTS = Hosts(
    structures=[
        Structure(
            identifier="@kabinet/app",
            label="App",
            description="An installable app (a containerized tool or plugin) in the hub's app catalog, known by its reverse-domain identifier, e.g. live.arkitekt.segmentation.",
        ),
        Structure(
            identifier="@kabinet/release",
            label="Release",
            description="One version of an app: a numbered release (e.g. 0.1.0) or the latest build of a channel (e.g. main), bundling the flavours that can be deployed for it.",
            descriptors=RELEASE_DESCRIPTORS,
        ),
        Structure(
            identifier="@kabinet/flavour",
            label="Flavour",
            description="A runnable variant of a release, e.g. vanilla or CUDA: one Docker image of the app's container, with the hardware selectors and services it needs.",
            descriptors=FLAVOUR_DESCRIPTORS,
        ),
        Structure(
            identifier="@kabinet/definition",
            label="Definition",
            description="An action definition: an action a flavour implements, with what it takes and returns, as rekuest will see it once the flavour runs; identified by its hash.",
            descriptors=DEFINITION_DESCRIPTORS,
        ),
        Structure(
            identifier="@kabinet/deployment",
            label="Deployment",
            description="A deployment: the intent to run a flavour (a container image) on a deployer backend, made under a release approval.",
            descriptors=PLACEMENT_DESCRIPTORS,
        ),
        Structure(
            identifier="@kabinet/pod",
            label="Pod",
            description="A pod: a running instance (container) of a deployment, reported and kept up to date by its backend.",
            descriptors=PLACEMENT_DESCRIPTORS,
        ),
        Structure(
            identifier="@kabinet/githubrepo",
            label="GitHub Repository",
            description="A GitHub repository scanned for installable apps and their releases.",
        ),
    ],
    signals=[
        Signal(
            identifier="@kabinet/app",
            kinds=["CREATED"],
            description="An app was registered in the app catalog.",
        ),
        Signal(
            identifier="@kabinet/release",
            kinds=["CREATED", "UPDATED"],
            descriptors=_keys(RELEASE_DESCRIPTORS),
            description="An app release (a new version) was registered or refreshed.",
        ),
        Signal(
            identifier="@kabinet/flavour",
            kinds=["CREATED", "UPDATED"],
            descriptors=_keys(FLAVOUR_DESCRIPTORS),
            description="A flavour (a container image build of a release) was registered or refreshed.",
        ),
        Signal(
            identifier="@kabinet/definition",
            kinds=["CREATED", "UPDATED"],
            descriptors=_keys(DEFINITION_DESCRIPTORS),
            description="An action definition was registered or refreshed.",
        ),
        Signal(
            identifier="@kabinet/deployment",
            kinds=["CREATED", "UPDATED", "DELETED"],
            descriptors=_keys(PLACEMENT_DESCRIPTORS),
            description="A deployment was created, changed status or removed.",
        ),
        Signal(
            identifier="@kabinet/pod",
            kinds=["CREATED", "UPDATED", "DELETED"],
            descriptors=_keys(PLACEMENT_DESCRIPTORS),
            description="A pod (a running container of a deployment) was created, changed status or removed.",
        ),
        Signal(
            identifier="@kabinet/githubrepo",
            kinds=["CREATED", "DELETED"],
            description="A GitHub repository was added or removed.",
        ),
    ],
)


def render(facts: Facts) -> dict[str, JSON]:
    """This release's config for the hub ``facts`` describes."""
    document: dict[str, JSON] = blocks.server(facts)
    document["instance"] = blocks.instance(facts)
    hook = blocks.rekuest_hook(facts)
    if hook is not None:
        document["rekuest_hook"] = hook
    return document


contract = Contract(
    description=Description(
        name="kabinet",
        identifier="live.arkitekt.kabinet",
        summary="The apps a hub can install and run.",
        needs=Needs(scopes=SCOPES, roles=ROLES, storage=["media"], instance_key=True, peers=["rekuest"]),
        offers=Offers(endpoints={"rekuest_service": "_rekuest/service", "rekuest_hook": "_rekuest/hook"}),
        requires={"rekuest": ">=6"},
        hosts=HOSTS,
    ),
    settings=Settings,
    render=render,
    # How this service is started: there is no script beside it. `arkitekt-service serve`
    # (and `debug`) become these, so they get the container's signals themselves.
    serve=Start(("daphne", "-b", "0.0.0.0", "-p", "80", "--websocket_timeout", "-1", "kabinet_server.asgi:application")),
    debug=Start(("python", "manage.py", "runserver", "0.0.0.0:80")),
    jobs={
        "ensureadmin": Job(("ensureadmin",), "Create the operator account the config names"),
        "ensurerepos": Job(("ensurerepos",), "Register the repositories the config names"),
        "restore_descriptors": Job(("restore_descriptors",), "Store the descriptors of every flavour, release, definition, deployment and pod that misses one (--all: of every row)"),
        "restore_bloks": Job(("restore_bloks",), "Store what the bloks of every flavour draw where it has none stored (--all: of every flavour)"),
    },
    setup=("ensureadmin", "ensurerepos", "restore_descriptors", "restore_bloks"),
)
