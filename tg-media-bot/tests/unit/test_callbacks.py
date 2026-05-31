from app.bot.callbacks import AuthRetryCallback, MediaChoiceCallback


def test_media_callback_format() -> None:
    payload = MediaChoiceCallback(kind="video", job_id=42).pack()
    assert payload == "media:video:42"


def test_auth_callback_format() -> None:
    payload = AuthRetryCallback(action="retry", job_id=99).pack()
    assert payload == "auth:retry:99"
