from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


MediaKind = Literal["video", "audio"]
SendMediaType = Literal["video", "audio", "photo"]


@dataclass(slots=True)
class MediaInfoResult:
    title: str
    source: str
    duration: int | None
    has_video: bool
    has_audio: bool


@dataclass(slots=True)
class AuthContext:
    login: str | None
    password_or_token: str


@dataclass(slots=True)
class DownloadResult:
    media_path: Path
    media_type: SendMediaType
    title: str
    source: str
    duration: int | None
    size_bytes: int
