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
    "PORT": "5555",
}
AUTHENTIKATE = {
    **AUTHENTIKATE,
    "STATIC_TOKENS": {
        "test": {"sub": "1"},
        # A non-privileged user in a different organization, for cross-tenant
        # scoping/permission tests (see the other_org_context fixture). roles
        # must be set explicitly: StaticToken defaults roles to ["admin"].
        "othertest": {"sub": "9", "active_org": "other_org", "roles": []},
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

# Enable database access from async code in tests
DATABASE_ROUTERS = []

# Use in-memory channel layer for tests instead of Redis
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
