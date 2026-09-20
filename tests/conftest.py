from asgiref.sync import sync_to_async
import os
import time

import psycopg
import pytest
import pytest_asyncio
import yaml

from authentikate.models import Client, Organization, User, Membership
from django.contrib.contenttypes.management import create_contenttypes
from django.db.models.signals import post_migrate
from kante.context import HttpContext, UniversalRequest
from strawberry.http.temporal_response import TemporalResponse
from dokker import PortNotFoundError, testing

from tests.utils import build_relative_dir


def _wait_for_port(e, service: str, container_port: int, deadline_seconds: float = 30.0) -> int:
    """The host port docker published for ``service:container_port``, once the container is up."""
    deadline = time.monotonic() + deadline_seconds
    while True:
        try:
            return e.get_port(service, container_port)
        except PortNotFoundError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.2)


@pytest.fixture(scope="session")
def backend_stack():
    docker_compose_path = os.path.join(os.path.dirname(__file__), "integration", "docker-compose.yaml")

    # No `down()` before `up()`: `testing()` mints a fresh `dokker-test-<uuid>` project
    # every call, so downing it would only tear down the empty project this run just
    # named, never a predecessor. It read as protection and was a no-op.
    with testing(docker_compose_path) as e:
        e.up()

        # `initc` runs `rc alias set ... http://rustfs:9000` as its first step, but
        # compose only waits for rustfs's container to *start* (service_started), not
        # for it to accept connections — so without this it races rustfs and dies with
        # "connection refused". Gate it on rustfs's /health (200 once serving).
        # The host ports are *not* fixed (see the compose file): ask the running stack
        # which ones docker picked. `up()` can return before a container is running, and
        # compose prints nothing for one that is not up yet, so retry the lookup.
        rustfs_port = _wait_for_port(e, "rustfs", 9000)
        e.add_health_check(
            url=f"http://localhost:{rustfs_port}/health",
            service="rustfs",
            max_retries=30,
            timeout=1,  # ~30s total, matching the postgres deadline below
        )
        e.check_health()

        e.run("initc", command="python init.py")

        # The host port is *not* fixed: the compose file publishes 5432 with no host port,
        # so docker assigns a free one per run and this asks the running stack which it
        # got. That is the whole isolation story -- dokker mints a unique compose project
        # per run, but a pinned host port defeats it: two projects still cannot both bind
        # one host port, so every suite under mounts/ that pinned the same one collided
        # with its siblings and with any stack a crashed run left behind. `get_port` is
        # resolved inside the retry loop because `up()` can return before the container
        # is running.
        db_port = None
        deadline = time.monotonic() + 30
        while True:
            try:
                if db_port is None:
                    db_port = e.get_port("db", 5432)
                with psycopg.connect(
                    dbname="testdb",
                    user="test",
                    password="test",
                    host="localhost",
                    port=db_port,
                    connect_timeout=1,
                ) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT 1")
                break
            except (psycopg.OperationalError, PortNotFoundError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.2)

        yield {"db": db_port, "rustfs": rustfs_port}


@pytest.fixture(scope="session", autouse=True)
def embedding_model_warm():
    """Load the embedding model once per session, outside any test's DB transaction.

    Every save of a Definition embeds its text, so the first one would otherwise pay the
    model load (a one-time download into the Hugging Face cache on a cold box) inside a test.
    """
    from embeddings import engine

    engine.warm_up()
    yield


@pytest.fixture(scope="session")
def django_db_modify_db_settings(backend_stack):
    """Start the backend services, and point Django at the ports they came up on.

    pytest-django calls this before creating the test database, which is the only window
    in which the port can be set: `settings_test` is imported long before any fixture runs,
    so it cannot know a port docker had not assigned yet. Its `PORT` is a placeholder for a
    hand-started stack; under pytest this is what decides where the connection goes.
    """
    from django.conf import settings

    settings.DATABASES["default"]["PORT"] = str(backend_stack["db"])
    yield


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    # Every transaction=True test teardown flushes the DB and re-fires
    # post_migrate, which rebuilds all contenttypes and permissions from the
    # model registry (~1s per test). The rows never change between tests, so
    # snapshot them once and swap the rebuild for a bulk re-insert with the
    # original pks (keeps guardian FKs and the ContentType pk cache valid).
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    with django_db_blocker.unblock():
        contenttypes = list(ContentType.objects.all())
        permissions = list(Permission.objects.all())

    post_migrate.disconnect(dispatch_uid="django.contrib.auth.management.create_permissions")
    post_migrate.disconnect(create_contenttypes)

    def restore_contenttypes_and_permissions(sender, **kwargs):
        # post_migrate fires once per app config on flush; restore once.
        if getattr(sender, "label", None) != "contenttypes":
            return
        ContentType.objects.bulk_create(contenttypes, ignore_conflicts=True)
        Permission.objects.bulk_create(permissions, ignore_conflicts=True)

    post_migrate.connect(
        restore_contenttypes_and_permissions,
        dispatch_uid="tests.restore_contenttypes_and_permissions",
    )
    yield

    # The async tests run sync ORM code in asgiref's executor threads, whose
    # connections outlive the tests and block dropping the test database
    # ("database is being accessed by other users"). Kill them before
    # pytest-django's teardown drops the database. This is Postgres-specific;
    # the sqlite in-memory test DB has no such backends to terminate.
    from django.db import connections

    if connections["default"].vendor == "postgresql":
        with django_db_blocker.unblock():
            with connections["default"].cursor() as cursor:
                cursor.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND pid <> pg_backend_pid()"
                )
            connections.close_all()


@pytest.fixture(scope="function")
def authenticated_context(db, backend_stack):
    # Match the identity the static "test" token resolves to (see settings_test
    # STATIC_TOKENS + authentikate's token expansion), so the org/user on this
    # context is the same one the schema's AuthentikateExtension authenticates as
    # at resolve time — otherwise organization-scoped queries see no data.
    user, _ = User.objects.get_or_create(
        sub="1", iss="static_issuer", defaults={"username": "static_issuer_1"}
    )
    client, _ = Client.objects.get_or_create(client_id="oinsoins")
    org, _ = Organization.objects.get_or_create(slug="static_org")
    membership, _ = Membership.objects.get_or_create(
        user=user,
        organization=org,
    )

    request = UniversalRequest(
        _extensions={"token": "test"},
        _client=client,  # type: ignore
        _user=user,  # type: ignore
        _organization=org,  # type: ignore
    )
    request.set_membership(membership)  # type: ignore

    return HttpContext(request=request, response=TemporalResponse(), headers={"Authorization": "Bearer test"}, type="http")


@pytest.fixture(scope="function")
def other_org_context(db, backend_stack) -> HttpContext:
    """A context for a user in a different organization (static token "othertest")."""
    user, _ = User.objects.get_or_create(
        sub="9", iss="static_issuer", defaults={"username": "static_issuer_9"}
    )
    client, _ = Client.objects.get_or_create(client_id="oinsoins")
    org, _ = Organization.objects.get_or_create(slug="other_org")
    membership, _ = Membership.objects.get_or_create(
        user=user,
        organization=org,
    )

    request = UniversalRequest(
        _extensions={"token": "othertest"},
        _client=client,  # type: ignore
        _user=user,  # type: ignore
        _organization=org,  # type: ignore
    )
    request.set_membership(membership)  # type: ignore

    return HttpContext(request=request, response=TemporalResponse(), headers={"Authorization": "Bearer othertest"}, type="http")


@pytest.fixture(scope="function")
def simple_api_context(db, backend_stack) -> HttpContext:
    user, _ = User.objects.get_or_create(
        sub="1", iss="static_issuer", defaults={"username": "static_issuer_1"}
    )
    client, _ = Client.objects.get_or_create(client_id="oinsoins")
    org, _ = Organization.objects.get_or_create(slug="static_org")
    membership, _ = Membership.objects.get_or_create(
        user=user,
        organization=org,
    )

    request = UniversalRequest(
        _extensions={"token": "test"},
        _client=client,  # type: ignore
        _user=user,  # type: ignore
        _organization=org,  # type: ignore
    )
    request.set_membership(membership)  # type: ignore

    return HttpContext(request=request, response=TemporalResponse(), headers={"Authorization": "Bearer test"}, type="http")


@pytest_asyncio.fixture
async def built_chain(authenticated_context: HttpContext) -> dict:
    """Build a full App -> Release -> DockerImage -> Flavour -> Definition chain plus
    its GithubRepo, offline via parse_config (the path test_db_deployments proves stays
    network-free for a logo-less manifest). Returns the created ids for query tests.
    """
    from bridge.models import GithubRepo
    from bridge.repo.models import KabinetConfigFile
    from bridge.repo.db import parse_config

    org = authenticated_context.request.organization
    user = authenticated_context.request.user

    repo = await GithubRepo.objects.acreate(
        name="ome",
        creator=user,
        organization=org,
        repo="ome",
        user="arkitektio-apps",
        branch="main",
    )

    with open(build_relative_dir("deployments/deployments.yaml"), "r") as f:
        config = KabinetConfigFile(**yaml.safe_load(f))

    # `parse_config` is synchronous (it runs inside `transaction.atomic`), so it has
    # to be thrown to a thread from this async fixture.
    flavours = await sync_to_async(parse_config)(config, repo, org)
    return {"repo_id": str(repo.id), "flavour_id": str(flavours[0].id)}


@pytest_asyncio.fixture
async def flavour_id(built_chain: dict) -> str:
    """The Flavour id from the built chain, as a GraphQL id string."""
    return built_chain["flavour_id"]
