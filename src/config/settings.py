"""Typed settings read from the environment.

The real `.env` lives outside the repo; `ENV_FILE_PATH` points to it. Values are validated when
the settings are built, so a typo such as `SCREEN_MAX_JOBS_PER_CALL=abc` stops the server at
startup instead of failing in the middle of a tool call. Secrets are `SecretStr`: printing or
logging them shows `**********`.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_DB = "postgresql+psycopg://laburo:laburo@localhost:5432/laburo"
_LOCAL_TEST_DB = "postgresql+psycopg://laburo:laburo@localhost:5432/laburo_test"


class Settings(BaseSettings):
    # An empty value (`LLM_CLIENT_MODEL=`) means "not set", so the default applies.
    # Unknown variables are ignored: the real .env may hold settings for other tools.
    model_config = SettingsConfigDict(env_ignore_empty=True, extra="ignore")

    # --- Environment ---
    app_env: Literal["local", "production"] = "local"

    # --- HTTP server ---
    server_host: str = "127.0.0.1"  # the container sets 0.0.0.0; compose publishes loopback only
    server_port: int = Field(default=8000, ge=1, le=65535)

    # --- Database ---
    database_url: str = _LOCAL_DB
    test_database_url: str = _LOCAL_TEST_DB

    # --- LLM ---
    openai_api_key: SecretStr = SecretStr("")
    llm_base_model: str = "gpt-6-luna"
    llm_client_model: str = ""  # empty = base model
    llm_judge_model: str = ""  # empty = base model

    # --- Sources ---
    serpapi_api_key: SecretStr = SecretStr("")
    serpapi_monthly_cap: int = Field(default=200, ge=0)
    demo_mode: bool = False

    # --- Observability ---
    opik_api_key: SecretStr = SecretStr("")
    opik_project: str = ""
    opik_workspace: str = ""
    obs_capture_pii: bool = False

    # --- Security ---
    upload_signing_secret: SecretStr = SecretStr("")
    public_base_url: str = "http://localhost:8000"
    descope_project_id: str = ""

    # --- Limits and tuning ---
    max_new_jobs_per_search: int = Field(default=30, gt=0)
    screen_max_jobs_per_call: int = Field(default=15, gt=0)
    claim_stale_seconds: int = Field(default=300, gt=0)
    draft_lease_seconds: int = Field(default=300, gt=0)
    slow_tool_warning_seconds: int = Field(default=30, gt=0)
    llm_concurrency: int = Field(default=4, gt=0)
    extraction_batch_size: int = Field(default=1, gt=0)
    linking_chunk_size: int = Field(default=15, gt=0)
    job_max_age_days: int = Field(default=30, gt=0)
    default_max_commute_km: int = Field(default=30, gt=0)

    # --- Cost control (remote) ---
    daily_cost_ceiling_usd: float | None = Field(default=None, gt=0)

    @classmethod
    def from_env_file(cls, env_file: str | Path | None) -> Self:
        """Build the settings from one env file (`None` = environment variables only)."""
        # pyright does not see pydantic-settings' `_env_file` argument in the synthesized __init__.
        return cls(_env_file=env_file)  # pyright: ignore[reportCallIssue]

    @model_validator(mode="after")
    def _production_needs_secrets(self) -> Self:
        """Fail closed: production never starts with an empty secret."""
        if self.app_env == "production":
            missing = [
                name
                for name in ("openai_api_key", "upload_signing_secret")
                if not getattr(self, name).get_secret_value()
            ]
            if missing:
                raise ValueError(f"APP_ENV=production requires: {', '.join(missing)}")
        return self


@lru_cache
def get_settings() -> Settings:
    """Build the settings once per process, from the file named by `ENV_FILE_PATH`."""
    return Settings.from_env_file(os.environ.get("ENV_FILE_PATH") or None)
