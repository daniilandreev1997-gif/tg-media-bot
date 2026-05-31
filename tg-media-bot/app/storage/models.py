from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class CredentialRecord:
    user_id: int
    provider: str
    login: str | None
    password_or_token: str
    expires_at: datetime

    def is_expired(self, now: datetime | None = None) -> bool:
        check_time = now or datetime.now(tz=UTC)
        return self.expires_at <= check_time


@dataclass(slots=True)
class MediaInfo:
    title: str
    duration: int | None
    source: str
    available_video: bool
    available_audio: bool
