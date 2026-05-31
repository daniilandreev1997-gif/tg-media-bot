from aiogram.filters import Command
from aiogram.types import Message
from aiogram import Router

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


@router.message(Command("start"))
async def start_cmd(message: Message) -> None:
    await message.answer(START_TEXT)


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("mode"))
async def mode_cmd(message: Message, app_ctx: AppContext) -> None:
    user_id = message.from_user.id if message.from_user else None
    if user_id is None or user_id not in app_ctx.settings.admin_ids:
        await message.answer("Команда доступна только администратору.")
        return
    await message.answer(f"Текущий режим: {app_ctx.settings.bot_update_mode}")
