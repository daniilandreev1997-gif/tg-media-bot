from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import sys


def _bootstrap_import_path(package_name: str | None, file_path: str) -> None:
    """Allow running as module and as direct file path."""
    if package_name:
        return
    project_root = Path(file_path).resolve().parent.parent
    root_str = str(project_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


_bootstrap_import_path(__package__, __file__)

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.bot.context import AppContext
from app.bot.routers import build_router
from app.config import load_settings
from app.services.downloader import YtDlpDownloader
from app.services.queue import DownloadQueue
from app.storage.db import Database
from app.storage.repositories import CredentialStore, JobRepository, SettingsRepository, UserRepository


logger = logging.getLogger(__name__)


async def build_app_context(bot: Bot, settings) -> tuple[AppContext, Database]:
    db = Database(settings.db_path)
    await db.connect()
    await db.init_schema(settings.schema_path)

    users = UserRepository(db)
    jobs = JobRepository(db)
    settings_repo = SettingsRepository(db)
    credentials = CredentialStore(db, ttl_days=settings.credential_ttl_days)

    await settings_repo.set("bot_update_mode", settings.bot_update_mode)
    await settings_repo.set("max_duration_min", str(settings.max_duration_min))
    await settings_repo.set("max_file_mb", str(settings.max_file_mb))

    downloader = YtDlpDownloader(settings)
    queue = DownloadQueue(
        bot=bot,
        downloader=downloader,
        jobs=jobs,
        workers_count=settings.workers_count,
    )

    app_ctx = AppContext(
        settings=settings,
        users=users,
        jobs=jobs,
        credentials=credentials,
        settings_repo=settings_repo,
        downloader=downloader,
        queue=queue,
    )
    return app_ctx, db


async def run_polling(bot: Bot, dp: Dispatcher, app_ctx: AppContext) -> None:
    await bot.delete_webhook(drop_pending_updates=False)
    await app_ctx.queue.start()
    try:
        await dp.start_polling(bot, app_ctx=app_ctx)
    finally:
        await app_ctx.queue.stop()


async def run_webhook(bot: Bot, dp: Dispatcher, app_ctx: AppContext) -> None:
    settings = app_ctx.settings
    if settings.webhook_url is None:
        raise RuntimeError("WEBHOOK_BASE_URL is required for webhook mode")

    await bot.set_webhook(url=settings.webhook_url, secret_token=settings.webhook_secret)
    await app_ctx.queue.start()

    app = web.Application()
    handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.webhook_secret,
    )
    handler.register(app, path=settings.webhook_path)
    setup_application(app, dp, bot=bot, app_ctx=app_ctx)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.webhook_host, port=settings.webhook_port)

    try:
        await site.start()
        logger.info(
            "Webhook started on %s:%s%s",
            settings.webhook_host,
            settings.webhook_port,
            settings.webhook_path,
        )
        while True:
            await asyncio.sleep(3600)
    finally:
        await app_ctx.queue.stop()
        await bot.delete_webhook(drop_pending_updates=False)
        await runner.cleanup()


async def async_main() -> None:
    settings = load_settings()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(build_router())

    app_ctx, db = await build_app_context(bot, settings)

    try:
        if settings.bot_update_mode == "polling":
            await run_polling(bot, dp, app_ctx)
        else:
            await run_webhook(bot, dp, app_ctx)
    finally:
        await bot.session.close()
        await db.close()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
