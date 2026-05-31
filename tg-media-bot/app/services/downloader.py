from __future__ import annotations

from pathlib import Path
from typing import Any
import asyncio

try:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError
except ModuleNotFoundError:
    YoutubeDL = None

    class DownloadError(Exception):
        pass

from app.config import Settings
from app.services.limits import validate_limits
from app.services.source_adapters import (
    SourceAdapter,
    is_tiktok_photo_url,
    tiktok_photo_to_video_url,
)
from app.services.types import AuthContext, DownloadResult, MediaInfoResult


class AuthRequiredError(Exception):
    pass


class SourceUnsupportedError(Exception):
    pass


class DependencyMissingError(Exception):
    pass


class YtDlpDownloader:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._download_dir = settings.download_dir
        self._download_dir.mkdir(parents=True, exist_ok=True)

    async def inspect(self, url: str, adapter: SourceAdapter) -> MediaInfoResult:
        info = await asyncio.to_thread(
            self._extract_info,
            url,
            adapter,
            None,
            False,
            "video",
        )
        duration = info.get("duration")
        has_audio = self._has_audio_stream(info) if adapter.can_audio else False
        has_video = self._has_video_stream(info) if adapter.can_video else False
        return MediaInfoResult(
            title=str(info.get("title") or "Без названия"),
            source=adapter.name,
            duration=int(duration) if isinstance(duration, (int, float)) else None,
            has_video=has_video,
            has_audio=has_audio,
        )

    async def fetch_tiktok_photo_urls(
        self,
        url: str,
        adapter: SourceAdapter,
        auth_context: AuthContext | None,
    ) -> tuple[list[str], str]:
        candidates = [url]
        if is_tiktok_photo_url(url):
            converted = tiktok_photo_to_video_url(url)
            if converted not in candidates:
                candidates.insert(0, converted)

        last_error: Exception | None = None
        for candidate in candidates:
            try:
                info = await asyncio.to_thread(
                    self._extract_info,
                    candidate,
                    adapter,
                    auth_context,
                    False,
                    "tiktok_photo",
                )
                photo_urls = self._extract_photo_urls(info)
                title = str(info.get("title") or "TikTok photo")
                if photo_urls:
                    return photo_urls, title
            except Exception as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise last_error
        raise SourceUnsupportedError("Не удалось извлечь фото из TikTok по этой ссылке.")

    async def download(
        self,
        url: str,
        adapter: SourceAdapter,
        media_kind: str,
        auth_context: AuthContext | None,
    ) -> DownloadResult:
        if media_kind == "audio" and not adapter.can_audio:
            raise SourceUnsupportedError("Для этого источника аудио недоступно.")
        if media_kind == "video" and not adapter.can_video:
            raise SourceUnsupportedError("Для этого источника видео недоступно.")

        candidate_url = tiktok_photo_to_video_url(url) if is_tiktok_photo_url(url) else url
        try:
            info = await asyncio.to_thread(
                self._extract_info,
                candidate_url,
                adapter,
                auth_context,
                True,
                media_kind,
            )
        except DownloadError as exc:
            if media_kind != "video" or not self._is_mux_postprocessing_error(str(exc)):
                raise
            # Fallback to a progressive single-file format when ffmpeg merge fails.
            info = await asyncio.to_thread(
                self._extract_info,
                candidate_url,
                adapter,
                auth_context,
                True,
                "video_safe",
            )

        file_path = self._resolve_downloaded_file(info)
        if not file_path.exists():
            raise RuntimeError("Файл не найден после загрузки")

        duration = info.get("duration")
        duration_int = int(duration) if isinstance(duration, (int, float)) else None
        size_bytes = file_path.stat().st_size
        validate_limits(self._settings, duration_int, size_bytes)

        media_type = "audio" if media_kind == "audio" else "video"
        if file_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            media_type = "photo"

        return DownloadResult(
            media_path=file_path,
            media_type=media_type,
            title=str(info.get("title") or file_path.name),
            source=adapter.name,
            duration=duration_int,
            size_bytes=size_bytes,
        )

    async def build_vk_post_repost_text(
        self,
        url: str,
        adapter: SourceAdapter,
        auth_context: AuthContext | None,
    ) -> str:
        info = await asyncio.to_thread(
            self._extract_info,
            url,
            adapter,
            auth_context,
            False,
            "vk_post_repost",
        )
        return self._format_vk_post_repost_text(info, url)

    def _extract_info(
        self,
        url: str,
        adapter: SourceAdapter,
        auth_context: AuthContext | None,
        download: bool,
        media_kind: str,
    ) -> dict[str, Any]:
        if YoutubeDL is None:
            raise DependencyMissingError(
                "На сервере не установлен yt-dlp. Установите зависимости: pip install -e ."
            )
        options = self._build_options(adapter, auth_context, download, media_kind)
        with YoutubeDL(options) as ydl:
            try:
                info = ydl.extract_info(url, download=download)
                if info is None:
                    raise RuntimeError("Пустой ответ от источника")
                return ydl.sanitize_info(info)
            except DownloadError as exc:
                message = str(exc).lower()
                if "private" in message or "login" in message or "cookie" in message or "authentication" in message:
                    raise AuthRequiredError("Требуется авторизация для этого контента") from exc
                raise

    def _build_options(
        self,
        adapter: SourceAdapter,
        auth_context: AuthContext | None,
        download: bool,
        media_kind: str,
    ) -> dict[str, Any]:
        outtmpl = (self._download_dir / "%(id)s_%(title).80B.%(ext)s").as_posix()
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": media_kind != "vk_post_repost",
            "outtmpl": outtmpl,
            "nopart": True,
        }

        if media_kind == "audio":
            options["format"] = "bestaudio/best"
            options["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
        elif media_kind == "video":
            if adapter.name == "youtube":
                options["format"] = (
                    "best[ext=mp4][height<=1080][height>=720][acodec!=none][vcodec!=none]/"
                    "best[height<=1080][height>=720][acodec!=none][vcodec!=none]/"
                    "bestvideo[height<=1080][height>=720]+bestaudio[ext=m4a]/"
                    "bestvideo[height<=1080][height>=720]+bestaudio/"
                    "best[ext=mp4][acodec!=none][vcodec!=none]/"
                    "best[acodec!=none][vcodec!=none]/"
                    "bestvideo+bestaudio/best"
                )
            else:
                options["format"] = (
                    "best[ext=mp4][acodec!=none][vcodec!=none]/"
                    "best[acodec!=none][vcodec!=none]/"
                    "bestvideo+bestaudio/best"
                )
            options["merge_output_format"] = "mp4"
        elif media_kind == "video_safe":
            if adapter.name == "youtube":
                options["format"] = (
                    "best[ext=mp4][height<=1080][height>=720][acodec!=none][vcodec!=none]/"
                    "best[height<=1080][height>=720][acodec!=none][vcodec!=none]/"
                    "best[ext=mp4][acodec!=none][vcodec!=none]/best"
                )
            else:
                options["format"] = "best[ext=mp4]/best"

        if not download:
            options["skip_download"] = True

        if auth_context is not None and auth_context.login and auth_context.password_or_token:
            options["username"] = auth_context.login
            options["password"] = auth_context.password_or_token
        elif auth_context is not None and auth_context.password_or_token:
            options["http_headers"] = {
                "Authorization": f"Bearer {auth_context.password_or_token}",
            }

        if adapter.name == "yandex_music":
            options.setdefault("extractor_args", {}).update(
                {
                    "yandexmusic": {
                        "format": ["mp3"],
                    }
                }
            )
        return options

    @staticmethod
    def _format_vk_post_repost_text(info: dict[str, Any], fallback_url: str) -> str:
        title = str(info.get("title") or "VK пост").strip()
        description = str(info.get("description") or "").strip()
        uploader = str(info.get("uploader") or "").strip()
        source_url = str(info.get("webpage_url") or fallback_url).strip()

        video_count, audio_count = YtDlpDownloader._count_vk_post_entries(info.get("entries"))
        attach_parts: list[str] = []
        if video_count:
            attach_parts.append(f"видео: {video_count}")
        if audio_count:
            attach_parts.append(f"аудио: {audio_count}")
        attach_line = ", ".join(attach_parts)

        lines = ["Репост из VK", f"Пост: {title}"]
        if uploader:
            lines.append(f"Автор: {uploader}")
        if description:
            lines.extend(["", YtDlpDownloader._truncate(description, 3000)])
        if attach_line:
            lines.extend(["", f"Вложения: {attach_line}"])
        lines.extend(["", source_url])

        final_text = "\n".join(lines).strip()
        return YtDlpDownloader._truncate(final_text, 4096)

    @staticmethod
    def _count_vk_post_entries(entries: Any) -> tuple[int, int]:
        if not isinstance(entries, list):
            return 0, 0
        video_count = 0
        audio_count = 0
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            vcodec = entry.get("vcodec")
            acodec = entry.get("acodec")
            formats = entry.get("formats")
            is_audio_only = vcodec == "none" and (acodec not in (None, "none"))
            if not is_audio_only and isinstance(formats, list):
                is_audio_only = any(
                    isinstance(fmt, dict)
                    and fmt.get("vcodec") == "none"
                    and fmt.get("acodec") not in (None, "none")
                    for fmt in formats
                )
            if is_audio_only:
                audio_count += 1
            else:
                video_count += 1
        return video_count, audio_count

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 3)].rstrip() + "..."

    @staticmethod
    def _has_video_stream(info: dict[str, Any], min_video_height: int = 0) -> bool:
        def is_good_video(fmt: dict[str, Any]) -> bool:
            if fmt.get("vcodec") in (None, "none"):
                return False
            if min_video_height <= 0:
                return True
            height = fmt.get("height")
            return isinstance(height, (int, float)) and int(height) >= min_video_height

        formats = info.get("formats")
        if isinstance(formats, list):
            for fmt in formats:
                if not isinstance(fmt, dict):
                    continue
                if is_good_video(fmt):
                    return True
        requested = info.get("requested_formats")
        if isinstance(requested, list):
            for fmt in requested:
                if isinstance(fmt, dict) and is_good_video(fmt):
                    return True
        if info.get("vcodec") in (None, "none"):
            return False
        if min_video_height <= 0:
            return True
        height = info.get("height")
        return isinstance(height, (int, float)) and int(height) >= min_video_height

    @staticmethod
    def _has_audio_stream(info: dict[str, Any]) -> bool:
        formats = info.get("formats")
        if isinstance(formats, list):
            for fmt in formats:
                if not isinstance(fmt, dict):
                    continue
                if fmt.get("acodec") not in (None, "none"):
                    return True
        requested = info.get("requested_formats")
        if isinstance(requested, list):
            for fmt in requested:
                if isinstance(fmt, dict) and fmt.get("acodec") not in (None, "none"):
                    return True
        return info.get("acodec") not in (None, "none")

    @staticmethod
    def _extract_photo_urls(info: dict[str, Any]) -> list[str]:
        urls: list[str] = []
        thumbnail = info.get("thumbnail")
        if isinstance(thumbnail, str) and thumbnail.startswith("http"):
            urls.append(thumbnail)
        thumbs = info.get("thumbnails")
        if isinstance(thumbs, list):
            for thumb in thumbs:
                if not isinstance(thumb, dict):
                    continue
                url = thumb.get("url")
                if isinstance(url, str) and url.startswith("http"):
                    urls.append(url)
        dedup: list[str] = []
        seen: set[str] = set()
        for url in urls:
            normalized = url.split("?")[0]
            if normalized in seen:
                continue
            seen.add(normalized)
            dedup.append(url)
        return dedup

    @staticmethod
    def _is_mux_postprocessing_error(message: str) -> bool:
        lowered = message.lower()
        return "postprocessing" in lowered or "stream #1:0" in lowered or "ffmpeg" in lowered

    def _resolve_downloaded_file(self, info: dict[str, Any]) -> Path:
        requested = info.get("requested_downloads")
        if isinstance(requested, list) and requested:
            candidate = requested[0].get("filepath")
            if candidate:
                return Path(candidate)

        filename = info.get("_filename")
        if filename:
            return Path(filename)

        file_path = info.get("filepath")
        if file_path:
            return Path(file_path)

        entries = info.get("entries")
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                try:
                    return self._resolve_downloaded_file(entry)
                except RuntimeError:
                    continue

        raise RuntimeError("yt-dlp did not return filepath")
