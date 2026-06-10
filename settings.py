"""Shared configuration (non-module helper).

`Settings` is a plain, importable config object backed by environment variables
and an optional `.env` file. It holds no behavior — modules receive a `Settings`
instance from `app.py` (dependency injection of config) rather than reaching for a
global owned by another module.
"""

from __future__ import annotations

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, overridable via env (prefix ``YTS_``) or CLI flags."""

    model_config = SettingsConfigDict(
        env_prefix="YTS_", env_file=".env", extra="ignore"
    )

    # Model-agnostic identifier understood by ``init_chat_model``,
    # e.g. "anthropic:claude-haiku-4-5" or "openai:gpt-4o-mini".
    model: str = "anthropic:claude-haiku-4-5"
    temperature: float = 0.0

    # Transcripts longer than this many characters take the map-reduce path.
    chunk_chars: int = 8000

    summary_style: str = "bullets"  # "bullets" | "paragraph"
    summary_length: str = "medium"  # "short" | "medium" | "long"

    # Preferred transcript languages, in priority order.
    languages: list[str] = ["en"]

    @field_validator("languages", mode="before")
    @classmethod
    def _split_languages(cls, value: object) -> object:
        """Allow ``YTS_LANGUAGES=en,es`` (comma string) in addition to a list."""
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


def load_settings() -> Settings:
    """Load ``.env`` into the process environment, then build `Settings`.

    Loading the dotenv file here ensures provider SDK keys (``ANTHROPIC_API_KEY``,
    ``OPENAI_API_KEY``) are present in ``os.environ`` for the underlying clients.
    """
    load_dotenv()
    return Settings()
