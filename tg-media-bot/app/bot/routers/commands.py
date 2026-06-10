from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.context import AppContext

router = Router(name="commands")


START_TEXT = (
    "Что скачиваем, звёздочка?\n\n"
    "Как пользоваться ботом:\n\n"
    "1. Зайди на страницу с интересным роликом\n"
    "2. Нажми кнопку «Поделиться»\n"
    "3. Скопируй ссылку на видео\n"
    "4. Открой чат с ботом и отправь ссылку\n"
    "5. Бот отправит видео/фото/аудио прямо в Telegram\n"
    "6. В настоящий момент могу скачивать из:\n"
    "• Instagram\n"
    "• TikTok\n"
    "• YouTube\n"
    "Также музыку можно скинуть из Яндекс музыки или ВК"
)

HELP_TEXT = (
    "Примеры ссылок:\n"
    "• https://www.youtube.com/watch?v=...\n"
    "• https://www.tiktok.com/@.../video/...\n"
    "• https://www.tiktok.com/@.../photo/...\n"
    "• https://www.instagram.com/reel/...\n"
    "• https://music.yandex.ru/album/.../track/...\n"
    "• https://vk.com/...\n\n"
    "Лимиты:\n"
    "• Длительность: до 60 минут\n"
    "• Размер: до 500 МБ\n\n"
    "Дополнительно:\n"
    "• Для ссылки вида vk.com/wall... бот сделает репост поста с текстом и ссылкой\n\n"
    "Если ссылка приватная, бот запросит логин/пароль или токен и повторит загрузку."
)

SYSTEM_MESSAGE_PREFIX = "Системное сообщение:\n\n"
MAX_TELEGRAM_MESSAGE_LENGTH = 4096


async def _remember_user(message: Message, app_ctx: AppContext) -> None:
    if message.from_user is not None:
        await app_ctx.users.get_or_create(message.from_user.id)


def _extract_command_args(text: str | None) -> str:
    parts = (text or "").split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


@router.message(Command("start"))
async def start_cmd(message: Message, app_ctx: AppContext) -> None:
    await _remember_user(message, app_ctx)
    await message.answer(START_TEXT)


@router.message(Command("help"))
async def help_cmd(message: Message, app_ctx: AppContext) -> None:
    await _remember_user(message, app_ctx)
    await message.answer(HELP_TEXT)


@router.message(Command("mode"))
async def mode_cmd(message: Message, app_ctx: AppContext) -> None:
    await _remember_user(message, app_ctx)
    user_id = message.from_user.id if message.from_user else None
    if user_id is None or user_id not in app_ctx.settings.admin_ids:
        await message.answer("Команда доступна только администратору.")
        return
    await message.answer(f"Текущий режим: {app_ctx.settings.bot_update_mode}")


@router.message(Command("send"))
async def send_cmd(message: Message, bot: Bot, app_ctx: AppContext) -> None:
    await _remember_user(message, app_ctx)
    text = _extract_command_args(message.text)
    if not text:
        await message.answer("Использование: /send текст сообщения")
        return

    system_text = f"{SYSTEM_MESSAGE_PREFIX}{text}"
    if len(system_text) > MAX_TELEGRAM_MESSAGE_LENGTH:
        max_text_length = MAX_TELEGRAM_MESSAGE_LENGTH - len(SYSTEM_MESSAGE_PREFIX)
        await message.answer(f"Сообщение слишком длинное. Лимит для текста: {max_text_length} символов.")
        return

    user_tg_ids = await app_ctx.users.list_telegram_ids()
    if not user_tg_ids:
        await message.answer("Некому отправлять: список пользователей пуст.")
        return

    delivered = 0
    failed = 0
    for user_tg_id in user_tg_ids:
        try:
            await bot.send_message(chat_id=user_tg_id, text=system_text, parse_mode=None)
        except TelegramAPIError:
            failed += 1
        else:
            delivered += 1

    await message.answer(f"Рассылка завершена. Отправлено: {delivered}. Ошибок: {failed}.")
