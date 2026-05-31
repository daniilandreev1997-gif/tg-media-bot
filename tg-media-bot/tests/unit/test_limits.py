from pathlib import Path

import pytest

from app.config import Settings
from app.services.limits import LimitError, validate_limits


def _settings() -> Settings:
    return Settings(
        bot_token="token",
        bot_update_mode="polling",
        webhook_base_url=None,
        webhook_secret=None,
        webhook_host="0.0.0.0",
        webhook_port=8080,
        webhook_path="/telegram/webhook",
        admin_ids=set(),
        max_duration_min=60,
        max_file_mb=500,
        credential_ttl_days=7,
        workers_count=1,
        download_dir=Path("."),
        db_path=Path("bot.db"),
        schema_path=Path("schema.sql"),
    )


def test_validate_limits_ok() -> None:
    settings = _settings()
    validate_limits(settings, duration=120, size_bytes=10 * 1024 * 1024)


def test_validate_limits_duration_error() -> None:
    settings = _settings()
    with pytest.raises(LimitError):
        validate_limits(settings, duration=60 * 61, size_bytes=None)


def test_validate_limits_size_error() -> None:
    settings = _settings()
    with pytest.raises(LimitError):
        validate_limits(settings, duration=30, size_bytes=(501 * 1024 * 1024))
