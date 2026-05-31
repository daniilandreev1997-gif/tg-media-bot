from __future__ import annotations

from app.config import Settings


class LimitError(Exception):
    pass


def validate_limits(settings: Settings, duration: int | None, size_bytes: int | None) -> None:
    if duration is not None and duration > settings.max_duration_min * 60:
        raise LimitError(
            f"Длительность превышает лимит ({settings.max_duration_min} мин)."
        )
    if size_bytes is not None and size_bytes > settings.max_file_bytes:
        raise LimitError(
            f"Размер превышает лимит ({settings.max_file_mb} МБ)."
        )
