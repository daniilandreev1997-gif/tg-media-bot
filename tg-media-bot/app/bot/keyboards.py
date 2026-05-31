from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks import AuthRetryCallback, MediaChoiceCallback


def auth_retry_keyboard(job_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Повторить с авторизацией",
                    callback_data=AuthRetryCallback(action="retry", job_id=job_id).pack(),
                )
            ]
        ]
    )


def media_choice_keyboard(job_id: int, has_video: bool, has_audio: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    buttons: list[InlineKeyboardButton] = []
    if has_video:
        buttons.append(
            InlineKeyboardButton(
                text="Видео",
                callback_data=MediaChoiceCallback(kind="video", job_id=job_id).pack(),
            )
        )
    if has_audio:
        buttons.append(
            InlineKeyboardButton(
                text="Аудио",
                callback_data=MediaChoiceCallback(kind="audio", job_id=job_id).pack(),
            )
        )
    if buttons:
        rows.append(buttons)
    rows.extend(auth_retry_keyboard(job_id).inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=rows)
