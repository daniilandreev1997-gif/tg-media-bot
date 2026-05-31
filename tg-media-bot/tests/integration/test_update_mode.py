from pathlib import Path

import pytest

from app.config import load_settings


def _set_base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "dummy_token")
    monkeypatch.setenv("MAX_DURATION_MIN", "60")
    monkeypatch.setenv("MAX_FILE_MB", "500")
    monkeypatch.setenv("CREDENTIAL_TTL_DAYS", "7")
    monkeypatch.setenv("WORKERS_COUNT", "1")
    monkeypatch.setenv("DOWNLOAD_DIR", "./data/downloads")
    monkeypatch.setenv("DB_PATH", "./data/bot.db")


def test_polling_mode_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("BOT_UPDATE_MODE", "polling")
    monkeypatch.delenv("WEBHOOK_BASE_URL", raising=False)

    settings = load_settings()
    assert settings.bot_update_mode == "polling"


def test_webhook_mode_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("BOT_UPDATE_MODE", "webhook")
    monkeypatch.setenv("WEBHOOK_BASE_URL", "https://example.com")

    settings = load_settings()
    assert settings.bot_update_mode == "webhook"
    assert settings.webhook_url == "https://example.com/telegram/webhook"


def test_webhook_mode_requires_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("BOT_UPDATE_MODE", "webhook")
    monkeypatch.delenv("WEBHOOK_BASE_URL", raising=False)

    with pytest.raises(ValueError):
        load_settings()
