"""Which HTTP options each mode gets: the Host/Origin guard is always on."""

from src.config.settings import Settings
from src.server import http_options


def _settings(**overrides: object) -> Settings:
    return Settings.from_env_file(None).model_copy(update=overrides)


def test_local_allows_loopback_hosts_and_keeps_sessions():
    options = http_options(_settings())
    assert options["host_origin_protection"] is True
    assert options["allowed_hosts"] == [
        "127.0.0.1:8000",
        "localhost:8000",
    ]
    assert options["stateless_http"] is False


def test_production_is_stateless_and_allows_the_public_host():
    options = http_options(
        _settings(app_env="production", public_base_url="https://laburo.example.com")
    )
    assert options["stateless_http"] is True
    assert "laburo.example.com" in options["allowed_hosts"]
    assert options["host_origin_protection"] is True


def test_the_allowed_local_port_follows_the_setting():
    assert "localhost:9100" in http_options(_settings(server_port=9100))["allowed_hosts"]
