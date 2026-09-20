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
# Django forces DEBUG=False under the test runner, and authentikate 3.0 refuses static
# tokens when DEBUG is False. These are deliberate test fixtures, so opt in explicitly.
AUTHENTIKATE = {
    **AUTHENTIKATE,
    "allow_static_tokens_in_production": True,
    "static_tokens": {
        "test": {"sub": "1"},
        # A non-privileged user in a different organization, for cross-tenant
        # scoping/permission tests (see the other_org_context fixture). roles
        # must be set explicitly: StaticToken defaults roles to ["admin"].
        "othertest": {"sub": "9", "org": "other_org", "roles": []},
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

# The embedding healer re-embeds stale rows in the background. Tests call
# ``embeddings.healer.reembed_stale`` explicitly instead, so a pass can never race an assertion.
EMBEDDINGS_HEALER_ENABLED = False
