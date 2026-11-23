"""Typed, fully-documented configuration schema for the **kabinet** service.

Owned by this service. Values resolve (highest precedence first) from init
kwargs, environment variables (nested via ``__`` — e.g. ``POSTGRES__PASSWORD``),
then the YAML file (``config.yaml`` where the service runs by default; override with
``ARKITEKT_CONFIG_FILE``). Secret fields have **no default**: loading fails fast
with a ``ValidationError`` if they are not supplied via config or environment.
"""

from arkitekt_service.server import settings as shared
from arkitekt_service.server.settings import (
    DjangoSettings,
    InstanceSettings,
    PostgresSettings,
    ServiceSettings,
)
from authentikate.base_models import AuthentikateSettings
from pydantic import BaseModel, ConfigDict, Field, field_validator

#: The apps the Arkitekt team publishes, served by arkitekt.live (arkitektio/arkitektio.github.io).
DEFAULT_CATALOG = "https://arkitekt.live/catalogs/default.json"


class RedisSettings(shared.RedisSettings):
    """Redis connection (channel layer / cache)."""

    channel_prefix: str = Field(
        default="kabinet",
        description=(
            "Key prefix for the channels_redis channel layer. Must be unique per service: "
            "every service on a shared redis used to send under the same prefix, so "
            'identically-named groups (e.g. "files") delivered one service\'s events to '
            "another's subscribers."
        ),
    )


class EmbeddingsSettings(BaseModel):
    """Semantic search: a model2vec static model embeds name + description into pgvector columns.

    Every value has a default, so the block may be omitted. The vector width is fixed by the
    model *and* by the database columns; see CONFIG.md before changing ``model``.
    """

    model_config = ConfigDict(extra="allow", protected_namespaces=())

    enabled: bool = Field(
        default=True,
        description="Embed rows on save and give `search` a semantic leg. Off: `search` is lexical-only and the embedding columns stay NULL.",
    )
    model: str = Field(
        default="minishlab/potion-base-8M",
        description="model2vec model id. Recorded on every row; rows embedded by another model are re-embedded in-process and skipped by vector search until then.",
    )
    model_path: str | None = Field(
        default=None,
        description="Directory holding the weights of `model` (save_pretrained layout). The Docker image bakes them under /opt/models and sets EMBEDDINGS__MODEL_PATH; unset, model2vec downloads from Hugging Face on first use.",
    )
    dimensions: int = Field(
        default=256,
        description="Vector width of `model`. Also the width of the database columns, so changing it is a migration. Checked against both at startup.",
    )
    distance_threshold: float = Field(
        default=0.55,
        description="Cosine distance (0 identical, 1 unrelated) above which a row no longer counts as a semantic `search` hit.",
    )
    sweep_interval: int = Field(
        default=300,
        description="No longer used: `reembed_stale` (which re-embeds rows whose `embedding_model` is not `model`) is only offered as an action, and scheduling it is the organization's own automation. Kept so existing configs load.",
    )
    sweep_batch_size: int = Field(default=200, description="Rows re-embedded per pass.")


class RekuestHookSettings(BaseModel):
    """How this process reaches the hub's rekuest: as a service (``rekuest_service``) and as a hook agent (``rekuest_hook``)."""

    rekuest_url: str = Field(
        default="http://rekuest:80/rekuest",
        description="rekuest's base URL on the internal network; runs are reported to its `agi/http/<agent>` intake.",
    )
    service: str = Field(
        default="kabinet",
        description="The name rekuest knows this process by: its `rekuest.services[].name` (signals are sent as it) and its `rekuest.hook_agents[].name`.",
    )
    max_skew: int = Field(
        default=30,
        description="Clock skew (seconds) tolerated on a signed request; tokens themselves live 60 s.",
    )


class Settings(ServiceSettings):
    """Top-level, validated configuration for the kabinet service."""

    django: DjangoSettings = Field(description="Core Django settings.")
    postgres: PostgresSettings = Field(description="PostgreSQL connection.")
    redis: RedisSettings = Field(description="Redis connection.")
    authentikate: AuthentikateSettings = Field(
        description="Token-verification config (authentikate)."
    )
    ensure_catalogs: list[str] = Field(
        default_factory=lambda: [DEFAULT_CATALOG],
        description="The catalogs every organization of this hub reads: URLs of curated repository lists (JSON or YAML, see docs/catalogs.md). Defaults to arkitekt.live's list; `[]` names none. An organization gets them when it lists its catalogs, cannot remove them, and adds its own beside them.",
    )

    @field_validator("ensure_catalogs")
    @classmethod
    def _catalog_urls(cls, value: list[str]) -> list[str]:
        for url in value:
            if not url.startswith(("https://", "http://")):
                raise ValueError(f"'{url}' is not an http(s) URL of a catalog")
        return value

    catalog_ttl: int = Field(
        default=3600,
        description="Seconds a catalog is not read again when its organization lists its catalogs; `refreshCatalog` reads one at once.",
    )
    embeddings: EmbeddingsSettings = Field(
        default_factory=EmbeddingsSettings,
        description="Semantic search model and thresholds.",
    )
    rekuest_hook: RekuestHookSettings | None = Field(
        default=None,
        description="Let the hub's rekuest run this service's periodic work (`reembed_stale`). Without it stale embeddings are not healed.",
    )
    instance: InstanceSettings | None = Field(
        default=None,
        description="This instance's key and the hub trust bundle (signed requests to and from rekuest, no shared secrets).",
    )
