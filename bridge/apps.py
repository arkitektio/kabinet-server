from django.apps import AppConfig


class BridgeConfig(AppConfig):
    """Django app configuration for the bridge app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "bridge"

    def ready(self) -> None:
        import bridge.signals  # noqa: F401
