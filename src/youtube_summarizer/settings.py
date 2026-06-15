"""
Shared configuration (non-module helper).

Secrets come from the environment (`.env`); non-secret preferences come from a JSON
config file resolved by `resolve_config_path`. Precedence is CLI/init args > env
vars > `.env` > JSON file > defaults.
"""

import json
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from platformdirs import user_config_dir
from pydantic import field_validator
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    SettingsConfigDict,
)

APP_NAME = "youtube-summarizer"

# Non-secret preference fields persisted to the JSON config file
CONFIG_FIELDS = (
    "model",
    "temperature",
    "chunk_chars",
    "summary_style",
    "summary_length",
    "languages",
)

# Choice presets surfaced by the interactive settings editor, each mapped to a
# short blurb describing how it differs from the others
MODEL_PRESETS = {
    "anthropic:claude-haiku-4-5": "fast, cheap Anthropic default",
    "anthropic:claude-sonnet-4-6": "balanced Anthropic; stronger quality",
    "anthropic:claude-opus-4-8": "most capable Anthropic; slowest, priciest",
    "openai:gpt-4o-mini": "cheap, reliable OpenAI workhorse",
    "openai:gpt-4.1-nano": "cheaper, faster than 4o-mini",
    "openai:gpt-5-nano": "cheapest, fastest GPT-5 tier",
    "google_genai:gemini-3.1-flash-lite": "free tier; cheapest, fastest Gemini",
    "google_genai:gemini-3.5-flash": "free tier; strong Gemini Flash",
}
STYLE_CHOICES = ("bullets", "paragraph")
LENGTH_CHOICES = ("short", "medium", "long")


def resolve_config_path() -> Path:
    """
    Resolve the active JSON config path: `YTS_CONFIG`, else a repo-local
    `settings.dev.json`, else the per-user config file.
    """
    env_path = os.environ.get("YTS_CONFIG")
    if env_path:
        return Path(env_path)

    dev_path = Path("settings.dev.json")
    if dev_path.is_file():
        return dev_path

    return Path(user_config_dir(APP_NAME)) / "settings.json"


class Settings(BaseSettings):
    """
    Runtime configuration: secrets from env, preferences from JSON, overridable per run.
    """
    model_config = SettingsConfigDict(
        env_prefix="YTS_", env_file=".env", extra="ignore"
    )

    # Model-agnostic identifier understood by `init_chat_model`,
    # e.g. "anthropic:claude-haiku-4-5" or "openai:gpt-4o-mini"
    model: str = "anthropic:claude-haiku-4-5"
    temperature: float = 0.0

    # Transcripts longer than this many characters take the map-reduce path
    chunk_chars: int = 8000

    summary_style: str = "bullets"  # "bullets" | "paragraph"
    summary_length: str = "medium"  # "short" | "medium" | "long"

    # Preferred transcript languages, in priority order
    languages: list[str] = ["en"]

    @field_validator("languages", mode="before")
    @classmethod
    def _split_languages(cls, value: object) -> object:
        """
        Allow `YTS_LANGUAGES=en,es` (comma string) in addition to a list.
        """
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """
        Layer the JSON config below env/`.env` so CLI > env > JSON > defaults.
        """
        sources = [init_settings, env_settings, dotenv_settings]
        json_path = resolve_config_path()
        if json_path.is_file():
            sources.append(
                JsonConfigSettingsSource(settings_cls, json_file=json_path)
            )
        return tuple(sources)


def load_settings() -> Settings:
    """
    Load `.env` into the process environment, then build `Settings` from all sources.

    Loading the dotenv file makes provider SDK keys (`ANTHROPIC_API_KEY`,
    `OPENAI_API_KEY`) available in `os.environ` for the underlying clients.
    """
    load_dotenv()
    return Settings()


def load_config() -> dict:
    """
    Read the non-secret preferences from the active JSON config file ({} if absent).
    """
    path = resolve_config_path()
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_config(values: dict) -> Path:
    """
    Atomically write `values` to the active JSON config file, returning its path.

    Writes to a temp file in the same directory, fsyncs it, then `os.replace`s it
    into place — a single atomic operation, so the config never ends up half-written.
    """
    path = resolve_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = tempfile.NamedTemporaryFile(
        "w",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
    )
    try:
        json.dump(values, tmp, indent=2, sort_keys=True)
        tmp.write("\n")
        tmp.flush()
        os.fsync(tmp.fileno())
    finally:
        tmp.close()

    os.replace(tmp.name, path)
    return path
