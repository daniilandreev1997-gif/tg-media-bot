from pathlib import Path

from app.config import Settings
from app.services.downloader import YtDlpDownloader


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


def test_format_vk_post_repost_text_contains_core_fields() -> None:
    info = {
        "title": "Wall post",
        "description": "Post body",
        "uploader": "VK Community",
        "webpage_url": "https://vk.com/wall-1_2",
        "entries": [
            {"vcodec": "none", "acodec": "mp3"},
            {"vcodec": "h264", "acodec": "aac"},
        ],
    }

    text = YtDlpDownloader._format_vk_post_repost_text(info, "https://vk.com/wall-1_2")

    assert "VK" in text
    assert "Wall post" in text
    assert "VK Community" in text
    assert "Post body" in text
    assert "1" in text
    assert text.endswith("https://vk.com/wall-1_2")


def test_format_vk_post_repost_text_truncates_to_telegram_limit() -> None:
    long_text = "x" * 10000
    info = {
        "title": "Wall post",
        "description": long_text,
        "webpage_url": "https://vk.com/wall-1_2",
        "entries": [],
    }

    text = YtDlpDownloader._format_vk_post_repost_text(info, "https://vk.com/wall-1_2")
    assert len(text) <= 4096


def test_count_vk_post_entries_from_formats() -> None:
    entries = [
        {"formats": [{"vcodec": "none", "acodec": "mp3"}]},
        {"formats": [{"vcodec": "h264", "acodec": "aac"}]},
    ]

    video_count, audio_count = YtDlpDownloader._count_vk_post_entries(entries)
    assert video_count == 1
    assert audio_count == 1


def test_vk_post_options_allow_playlist_and_skip_format_selection() -> None:
    downloader = YtDlpDownloader(_settings())
    options = downloader._build_options(
        adapter=type("A", (), {"name": "vk"})(),
        auth_context=None,
        download=False,
        media_kind="vk_post_repost",
    )

    assert options["noplaylist"] is False
    assert "format" not in options


def test_youtube_video_options_require_720p_or_higher() -> None:
    downloader = YtDlpDownloader(_settings())
    options = downloader._build_options(
        adapter=type("A", (), {"name": "youtube"})(),
        auth_context=None,
        download=True,
        media_kind="video",
    )

    fmt = options["format"]
    assert "height>=720" in fmt
    assert "best[ext=mp4][acodec!=none][vcodec!=none]" in fmt
    assert options["merge_output_format"] == "mp4"


def test_resolve_downloaded_file_from_playlist_entries() -> None:
    downloader = YtDlpDownloader(_settings())
    info = {
        "_type": "playlist",
        "entries": [
            {
                "requested_downloads": [
                    {
                        "filepath": "/tmp/example.mp4",
                    }
                ]
            }
        ],
    }
    path = downloader._resolve_downloaded_file(info)
    assert path.as_posix() == "/tmp/example.mp4"


def test_has_video_stream_false_for_audio_only_tiktok_photo_fallback() -> None:
    info = {
        "formats": [
            {"format_id": "audio", "vcodec": "none", "acodec": "mp3"},
        ]
    }
    assert not YtDlpDownloader._has_video_stream(info)
    assert YtDlpDownloader._has_audio_stream(info)


def test_has_video_stream_with_min_height_filter() -> None:
    info = {
        "formats": [
            {"format_id": "18", "vcodec": "h264", "acodec": "aac", "height": 360},
            {"format_id": "22", "vcodec": "h264", "acodec": "aac", "height": 720},
        ]
    }
    assert YtDlpDownloader._has_video_stream(info, min_video_height=720)
    assert not YtDlpDownloader._has_video_stream(info, min_video_height=1080)


def test_extract_photo_urls_deduplicates_query_variants() -> None:
    info = {
        "thumbnail": "https://example.com/a.jpg?x=1",
        "thumbnails": [
            {"url": "https://example.com/a.jpg?x=2"},
            {"url": "https://example.com/b.jpg"},
        ],
    }
    urls = YtDlpDownloader._extract_photo_urls(info)
    assert urls == ["https://example.com/a.jpg?x=1", "https://example.com/b.jpg"]
