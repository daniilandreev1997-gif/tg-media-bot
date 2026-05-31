from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Literal

try:
    from dotenv import load_dotenv as _load_dotenv
except ModuleNotFoundError:
    def _load_dotenv(*_args, **_kwargs) -> bool:
        return False

UpdateMode = Literal["polling", "webhook"]


@dataclass(slots=True)
class Settings:
    bot_token: str
    bot_update_mode: UpdateMode
    webhook_base_url: str | None
    webhook_secret: str | None
    webhook_host: str
    webhook_port: int
    webhook_path: str
    admin_ids: set[int]
    max_duration_min: int
    max_file_mb: int
    credential_ttl_days: int
    workers_count: int
    download_dir: Path
    db_path: Path
    schema_path: Path

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024

    @property
    def webhook_url(self) -> str | None:
        if not self.webhook_base_url:
            return None
        return f"{self.webhook_base_url.rstrip('/')}{self.webhook_path}"


def parse_update_mode(raw: str | None) -> UpdateMode:
    value = (raw or "polling").strip().lower()
    if value not in {"polling", "webhook"}:
        raise ValueError("BOT_UPDATE_MODE must be one of: polling, webhook")
    return value  # type: ignore[return-value]


def parse_admin_ids(raw: str | None) -> set[int]:
    if not raw:
        return set()
    result: set[int] = set()
    for chunk in raw.split(","):
        part = chunk.strip()
        if not part:
            continue
        result.add(int(part))
    return result


def _resolve_path(base_dir: Path, raw: str | None, default_rel: str) -> Path:
    value = Path(raw) if raw else Path(default_rel)
    if not value.is_absolute():
        value = base_dir / value
    return value.resolve()


def load_settings() -> Settings:
    base_dir = Path(__file__).resolve().parent.parent
    _load_dotenv(base_dir / ".env")

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise ValueError("BOT_TOKEN is required")

    settings = Settings(
        bot_token=bot_token,
        bot_update_mode=parse_update_mode(os.getenv("BOT_UPDATE_MODE")),
        webhook_base_url=os.getenv("WEBHOOK_BASE_URL"),
        webhook_secret=os.getenv("WEBHOOK_SECRET"),
        webhook_host=os.getenv("WEBHOOK_HOST", "0.0.0.0"),
        webhook_port=int(os.getenv("WEBHOOK_PORT", "8080")),
        webhook_path=os.getenv("WEBHOOK_PATH", "/telegram/webhook"),
        admin_ids=parse_admin_ids(os.getenv("ADMIN_IDS")),
        max_duration_min=int(os.getenv("MAX_DURATION_MIN", "60")),
        max_file_mb=int(os.getenv("MAX_FILE_MB", "500")),
        credential_ttl_days=int(os.getenv("CREDENTIAL_TTL_DAYS", "7")),
        workers_count=max(1, int(os.getenv("WORKERS_COUNT", "2"))),
        download_dir=_resolve_path(base_dir, os.getenv("DOWNLOAD_DIR"), "data/downloads"),
        db_path=_resolve_path(base_dir, os.getenv("DB_PATH"), "data/bot.db"),
        schema_path=(base_dir / "storage" / "migrations" / "001_init.sql").resolve(),
    )

    if settings.bot_update_mode == "webhook" and not settings.webhook_url:
        raise ValueError("WEBHOOK_BASE_URL is required when BOT_UPDATE_MODE=webhook")
    return settings
