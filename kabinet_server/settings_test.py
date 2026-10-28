import os
from .settings import *  # noqa
from .settings import DATABASES, AUTHENTIKATE
import logging

# Point at the Postgres brought up by the conftest backend_stack (see
# tests/integration/docker-compose.yaml — db on :5555, database "testdb").
DATABASES["default"] = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "testdb",
    "USER": "test",
    "PASSWORD": "test",
    "HOST": "localhost",
    # A placeholder for a hand-started stack; under pytest `django_db_modify_db_settings`
    # overwrites it with the port docker picked (see tests/conftest.py). Point
    # KABINET_TEST_DB_PORT at `docker compose port db 5432` to run against your own stack.
    "PORT": os.environ.get("KABINET_TEST_DB_PORT", "5555"),
}
#: What a test token is unless it says otherwise: kabinet's admin, through an app granted all of kabinet.
ADMIN_WITH_EVERY_SCOPE = {"roles": ["kabinet_admin"], "scope": "openid kabinet_all"}

# Django forces DEBUG=False under the test runner, and authentikate 3.0 refuses static
# tokens when DEBUG is False. These are deliberate test fixtures, so opt in explicitly.
AUTHENTIKATE = {
    **AUTHENTIKATE,
    "allow_static_tokens_in_production": True,
    "static_tokens": {
        name: {**ADMIN_WITH_EVERY_SCOPE, **token}
        for name, token in {
            "test": {"sub": "1"},
            # A non-privileged user in a different organization, for cross-tenant
            # scoping/permission tests (see the other_org_context fixture): a deployer,
            # every member's role, so it writes in its own organization but is not kabinet's admin.
            "othertest": {"sub": "9", "org": "other_org", "roles": ["kabinet_deployer"]},
            # An app granted only what it reads, for the scope tests (tests/test_scopes.py).
            "readertest": {"sub": "1", "scope": "openid kabinet_read"},
        }.items()
    },
}


# Disable migrations for faster tests
class DisableMigrations:
    """Disable migrations during testing for faster test execution."""

    def __contains__(self, item: str) -> bool:
        """Check if item is in migration modules."""
        return True

    def __getitem__(self, item: str) -> None:
        """Get migration module for item."""
        return None


# For faster test execution, you can uncomment this:
# MIGRATION_MODULES = DisableMigrations()

# Disable logging during tests to reduce noise
logging.disable(logging.CRITICAL)

# Don't auto-provision default/ensured GithubRepos when an Organization is
# created (see bridge.signals.ensure_default_repos_for_organization). The query
# tests build their own repo chains via fixtures and assert on exact contents,
# so any config-provisioned repo would leak in as an extra row.
DEFAULT_REPOS = []
ENSURED_REPOS = []

# Enable database access from async code in tests
DATABASE_ROUTERS = []

# Use in-memory channel layer for tests instead of Redis
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

