"""Typed, fully-documented configuration schema for the **kabinet** service.

Owned by this service. Values resolve (highest precedence first) from init
kwargs, environment variables (nested via ``__`` — e.g. ``POSTGRES__PASSWORD``),
then the YAML file (the mount's ``config.yaml`` by default; override with
``ARKITEKT_CONFIG_FILE``). Secret fields have **no default**: loading fails fast
with a ``ValidationError`` if they are not supplied via config or environment.
"""

import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from authentikate.base_models import AuthentikateSettings

_DEFAULT_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"
)


class AdminSettings(BaseModel):
    """Django superuser created on first boot."""

    username: str = Field(description="Superuser login name.")
    password: str = Field(description="Superuser password. Secret — must be set.")
    email: Optional[str] = Field(default=None, description="Superuser email address.")


class DjangoSettings(BaseModel):
    """Core Django framework settings."""

    secret_key: str = Field(description="Django SECRET_KEY for cryptographic signing. Secret — must be set.")
    debug: bool = Field(default=False, description="Enable Django debug mode (never in production).")
    hosts: List[str] = Field(default_factory=lambda: ["*"], description="ALLOWED_HOSTS entries.")
    use_x_forwarded_host: bool = Field(default=True, description="Trust the X-Forwarded-Host header behind a reverse proxy.")
    admin: Optional[AdminSettings] = Field(default=None, description="Superuser provisioned on first boot.")
    csrf_trusted_origins: List[str] = Field(default_factory=lambda: ["http://localhost", "https://localhost"], description="CSRF_TRUSTED_ORIGINS for unsafe (POST) requests.")
    force_script_name: str = Field(default="", description="URL path prefix (FORCE_SCRIPT_NAME) this service is served under.")


class PostgresSettings(BaseModel):
    """PostgreSQL database connection (Django ``DATABASES['default']``)."""

    model_config = ConfigDict(extra="allow")

    engine: str = Field(default="django.db.backends.postgresql", description="Django database backend (PostgreSQL).")
    db_name: str = Field(description="Database name.")
    username: str = Field(description="Database user.")
    password: str = Field(description="Database password. Secret — must be set.")
    host: str = Field(description="Database host.")
    port: int = Field(default=5432, description="Database port.")


class RedisSettings(BaseModel):
    """Redis connection (channel layer / cache)."""

    model_config = ConfigDict(extra="allow")

    host: str = Field(description="Redis host.")
    port: int = Field(default=6379, description="Redis port.")
    channel_prefix: str = Field(default="kabinet", description="Key prefix for the channels_redis channel layer. Must be unique per service: every service on a shared redis used to send under the same prefix, so identically-named groups (e.g. \"files\") delivered one service's events to another's subscribers.")


class EmbeddingsSettings(BaseModel):
    """Semantic search: a model2vec static model embeds name + description into pgvector columns.

    Every value has a default, so the block may be omitted. The vector width is fixed by the
    model *and* by the database columns; see CONFIG.md before changing ``model``.
    """

    model_config = ConfigDict(extra="allow", protected_namespaces=())

    enabled: bool = Field(default=True, description="Embed rows on save and give `search` a semantic leg. Off: `search` is lexical-only and the embedding columns stay NULL.")
    model: str = Field(default="minishlab/potion-base-8M", description="model2vec model id. Recorded on every row; rows embedded by another model are re-embedded in-process and skipped by vector search until then.")
    model_path: Optional[str] = Field(default=None, description="Directory holding the weights of `model` (save_pretrained layout). The Docker image bakes them under /opt/models and sets EMBEDDINGS__MODEL_PATH; unset, model2vec downloads from Hugging Face on first use.")
    dimensions: int = Field(default=256, description="Vector width of `model`. Also the width of the database columns, so changing it is a migration. Checked against both at startup.")
    distance_threshold: float = Field(default=0.55, description="Cosine distance (0 identical, 1 unrelated) above which a row no longer counts as a semantic `search` hit.")
    sweep_interval: int = Field(default=30, description="Seconds between in-process passes that re-embed rows whose `embedding_model` is not `model`.")
    sweep_batch_size: int = Field(default=200, description="Rows re-embedded per pass.")


class Settings(BaseSettings):
    """Top-level, validated configuration for the kabinet service."""

    model_config = SettingsConfigDict(env_nested_delimiter="__", extra="ignore")

    django: DjangoSettings = Field(description="Core Django settings.")
    postgres: PostgresSettings = Field(description="PostgreSQL connection.")
    redis: RedisSettings = Field(description="Redis connection.")
    authentikate: AuthentikateSettings = Field(description="Token-verification config (authentikate).")
    ensured_repos: List[str] = Field(default_factory=list, description="Container repos cloned/ensured on boot (``owner/repo:ref``).")
    repo_map: List[Dict[str, Any]] = Field(default_factory=list, description="Per-organization repository mappings.")
    default_repos: List[str] = Field(default_factory=list, description="Default repositories provisioned for new installs (``owner/repo:ref``).")
    embeddings: EmbeddingsSettings = Field(default_factory=EmbeddingsSettings, description="Semantic search model and thresholds.")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Precedence: explicit init kwargs > environment variables > YAML file.
        path = os.environ.get("ARKITEKT_CONFIG_FILE", _DEFAULT_CONFIG)
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls, yaml_file=path),
            file_secret_settings,
        )
