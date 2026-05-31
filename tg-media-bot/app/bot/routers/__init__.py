from aiogram import Router

from app.bot.routers.commands import router as commands_router
from app.bot.routers.media import router as media_router


def build_router() -> Router:
    root = Router(name="root")
    root.include_router(commands_router)
    root.include_router(media_router)
    return root
