from aiogram.filters.callback_data import CallbackData


class MediaChoiceCallback(CallbackData, prefix="media"):
    kind: str
    job_id: int


class AuthRetryCallback(CallbackData, prefix="auth"):
    action: str
    job_id: int
