from app.services.source_adapters import detect_source, is_vk_wall_post_url


def test_detect_instagram() -> None:
    adapter = detect_source("https://www.instagram.com/reel/abc123")
    assert adapter is not None
    assert adapter.name == "instagram"


def test_detect_tiktok() -> None:
    adapter = detect_source("https://www.tiktok.com/@user/video/123")
    assert adapter is not None
    assert adapter.name == "tiktok"


def test_detect_youtube() -> None:
    adapter = detect_source("https://youtu.be/dQw4w9WgXcQ")
    assert adapter is not None
    assert adapter.name == "youtube"


def test_detect_yandex_music() -> None:
    adapter = detect_source("https://music.yandex.ru/album/1/track/2")
    assert adapter is not None
    assert adapter.name == "yandex_music"


def test_detect_vk() -> None:
    adapter = detect_source("https://vk.com/video-1_2")
    assert adapter is not None
    assert adapter.name == "vk"


def test_detect_unsupported_returns_none() -> None:
    adapter = detect_source("https://example.com/video")
    assert adapter is None


def test_vk_wall_post_direct_url_detected() -> None:
    assert is_vk_wall_post_url("https://vk.com/wall-123_456")


def test_vk_wall_post_query_url_detected() -> None:
    assert is_vk_wall_post_url("https://vk.com/somepage?w=wall-123_456")


def test_vk_non_wall_url_is_not_wall_post() -> None:
    assert not is_vk_wall_post_url("https://vk.com/video-1_2")
