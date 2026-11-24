from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config.settings import Settings

SAMPLE_ENV = Path(__file__).parents[2] / ".env.sample"


def test_sample_env_loads_and_applies_defaults_for_empty_values():
    settings = Settings.from_env_file(SAMPLE_ENV)

    assert settings.llm_base_model == "gpt-6-luna"
    assert settings.llm_client_model == ""  # empty in the sample -> default
    assert settings.demo_mode is True
    assert settings.screen_max_jobs_per_call == 15
    assert settings.daily_cost_ceiling_usd is None


def test_secrets_are_masked_when_printed():
    settings = Settings.from_env_file(SAMPLE_ENV)

    assert "sk-fake-replace-me" not in repr(settings)
    assert settings.openai_api_key.get_secret_value() == "sk-fake-replace-me"


def test_invalid_number_stops_startup(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SCREEN_MAX_JOBS_PER_CALL", "abc")

    with pytest.raises(ValidationError):
        Settings.from_env_file(None)


def test_production_without_secrets_fails_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(ValidationError, match="upload_signing_secret"):
        Settings.from_env_file(None)
