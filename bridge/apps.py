from django.apps import AppConfig


class BridgeConfig(AppConfig):
    """Django app configuration for the bridge app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "bridge"

    def ready(self) -> None:
        """Connect the signal handlers and register the embedding system checks.

        The checks assert that the model's width, ``EMBEDDINGS.DIMENSIONS`` and the ``vector(N)``
        column agree; ``migrate`` runs the database-tagged one at every boot, so a mismatch
        stops the service before it serves a wrong search.
        """
        import bridge.signals  # noqa: F401
        import embeddings.checks  # noqa: F401
