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

#: What exists on a hub because this service is there: said here, as data, so the hub knows it from
#: the image. ``service.py`` binds each of these to its model and refuses anything not said here.
HOSTS = Hosts(
    structures=[
        Structure(
            identifier="@kabinet/app",
            label="App",
            description="An application, known by its reverse-domain identifier.",
        ),
        Structure(
            identifier="@kabinet/release",
            label="Release",
            description="One version of an app, bundling the flavours that can be deployed for it.",
            descriptors=[
                Descriptor(key="@kabinet/version", type="STRING", description="Its version"),
            ],
        ),
        Structure(
            identifier="@kabinet/flavour",
            label="Flavour",
            description="A runnable build of a release: one image, with the selectors and services it needs.",
            descriptors=[
                Descriptor(key="@kabinet/flavour", type="STRING", description="Which variant of its release it is, e.g. vanilla or cuda"),
                Descriptor(key="@kabinet/builder", type="STRING", description="The builder that produced its image"),
            ],
        ),
        Structure(
            identifier="@kabinet/definition",
            label="Definition",
            description="An action definition: what an action of a flavour takes and returns, by its hash.",
            descriptors=[
                Descriptor(key="@kabinet/kind", type="STRING", description="Whether it is a function or a generator"),
                Descriptor(key="@kabinet/scope", type="STRING", description="Where the data it works on lives, e.g. GLOBAL"),
                Descriptor(key="@kabinet/pure", type="BOOL", description="Whether its result may be cached"),
                Descriptor(key="@kabinet/idempotent", type="BOOL", description="Whether running it twice is the same as running it once"),
            ],
        ),
        Structure(
            identifier="@kabinet/deployment",
            label="Deployment",
            description="A flavour set to run on a backend.",
            descriptors=[
                Descriptor(key="@kabinet/status", type="STRING", description="Its lifecycle status"),
            ],
        ),
        Structure(
            identifier="@kabinet/pod",
            label="Pod",
            description="A running instance of a deployment on a backend.",
            descriptors=[
                Descriptor(key="@kabinet/status", type="STRING", description="Its lifecycle status"),
            ],
        ),
        Structure(
            identifier="@kabinet/githubrepo",
            label="Github Repo",
            description="A GitHub repository scanned for deployable apps.",
        ),
    ],
    signals=[
        Signal(
            identifier="@kabinet/app",
            kinds=["CREATED"],
            description="An app was registered.",
        ),
        Signal(
            identifier="@kabinet/release",
            kinds=["CREATED", "UPDATED"],
            descriptors=["@kabinet/version"],
            description="An app release was registered or refreshed.",
        ),
        Signal(
            identifier="@kabinet/flavour",
            kinds=["CREATED", "UPDATED"],
            descriptors=["@kabinet/flavour", "@kabinet/builder"],
            description="A flavour (a runnable build of a release) was registered or refreshed.",
        ),
        Signal(
            identifier="@kabinet/definition",
            kinds=["CREATED", "UPDATED"],
            descriptors=["@kabinet/kind", "@kabinet/scope", "@kabinet/pure", "@kabinet/idempotent"],
            description="An action definition was registered or refreshed.",
        ),
        Signal(
            identifier="@kabinet/deployment",
            kinds=["CREATED", "UPDATED", "DELETED"],
            descriptors=["@kabinet/status"],
            description="A deployment was created, changed status or removed.",
        ),
        Signal(
            identifier="@kabinet/pod",
            kinds=["CREATED", "UPDATED", "DELETED"],
            descriptors=["@kabinet/status"],
            description="A pod was created, changed status or removed.",
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
        "ensurerepos": Job(("ensurerepos",), "Register the repositories the config names"),
    },
    setup=("ensurerepos",),
)
