from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class SourceAdapter:
    name: str
    pattern: re.Pattern[str]
    provider: str
    can_audio: bool = True
    can_video: bool = True

    def detect(self, url: str) -> bool:
        return bool(self.pattern.search(url))


ADAPTERS: tuple[SourceAdapter, ...] = (
    SourceAdapter(
        name="instagram",
        pattern=re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/", re.IGNORECASE),
        provider="instagram",
    ),
    SourceAdapter(
        name="tiktok",
        pattern=re.compile(r"(?:https?://)?(?:www\.)?tiktok\.com/", re.IGNORECASE),
        provider="tiktok",
    ),
    SourceAdapter(
        name="youtube",
        pattern=re.compile(
            r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)",
            re.IGNORECASE,
        ),
        provider="youtube",
    ),
    SourceAdapter(
        name="yandex_music",
        pattern=re.compile(r"(?:https?://)?music\.yandex\.(?:ru|com)/", re.IGNORECASE),
        provider="yandex_music",
        can_video=False,
        can_audio=True,
    ),
    SourceAdapter(
        name="vk",
        pattern=re.compile(r"(?:https?://)?(?:www\.)?(?:vk\.com|m\.vk\.com)/", re.IGNORECASE),
        provider="vk",
        can_audio=True,
        can_video=True,
    ),
)

VK_WALL_POST_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.|m\.)?vk\.com/"
    r"(?:wall-?\d+_\d+(?:\?.*)?|[^?\s]+\?(?:.*&)?w=wall-?\d+_\d+(?:.*)?)",
    re.IGNORECASE,
)
TIKTOK_PHOTO_PATTERN = re.compile(
    r"(?P<prefix>(?:https?://)?(?:www\.)?tiktok\.com/@[^/\s]+/)"
    r"photo/(?P<id>\d+)(?P<suffix>(?:\?.*)?)$",
    re.IGNORECASE,
)


def detect_source(url: str) -> SourceAdapter | None:
    for adapter in ADAPTERS:
        if adapter.detect(url):
            return adapter
    return None


def is_vk_wall_post_url(url: str) -> bool:
    return bool(VK_WALL_POST_PATTERN.search(url))


def is_tiktok_photo_url(url: str) -> bool:
    return bool(TIKTOK_PHOTO_PATTERN.search(url.strip()))


def tiktok_photo_to_video_url(url: str) -> str:
    match = TIKTOK_PHOTO_PATTERN.search(url.strip())
    if not match:
        return url
    return f"{match.group('prefix')}video/{match.group('id')}{match.group('suffix') or ''}"
