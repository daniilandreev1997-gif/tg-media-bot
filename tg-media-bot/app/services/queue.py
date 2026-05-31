from __future__ import annotations

from dataclasses import dataclass
import asyncio
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile

from app.bot.keyboards import auth_retry_keyboard
from app.services.downloader import (
    AuthRequiredError,
    DependencyMissingError,
    SourceUnsupportedError,
    YtDlpDownloader,
)
from app.services.limits import LimitError
from app.services.source_adapters import SourceAdapter
from app.services.types import AuthContext
from app.storage.repositories import JobRepository


@dataclass(slots=True)
class DownloadTask:
    job_id: int
    chat_id: int
    url: str
    adapter: SourceAdapter
    media_kind: str
    auth_context: AuthContext | None = None


class DownloadQueue:
    def __init__(
        self,
        bot: Bot,
        downloader: YtDlpDownloader,
        jobs: JobRepository,
        workers_count: int,
    ):
        self._bot = bot
        self._downloader = downloader
        self._jobs = jobs
        self._queue: asyncio.Queue[DownloadTask | None] = asyncio.Queue()
        self._workers_count = workers_count
        self._workers: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        if self._workers:
            return
        for idx in range(self._workers_count):
            task = asyncio.create_task(self._worker_loop(idx), name=f"download-worker-{idx}")
            self._workers.append(task)

    async def stop(self) -> None:
        if not self._workers:
            return
        for _ in self._workers:
            await self._queue.put(None)
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def enqueue(self, task: DownloadTask) -> None:
        await self._queue.put(task)

    async def _worker_loop(self, worker_id: int) -> None:
        del worker_id
        while True:
            task = await self._queue.get()
            if task is None:
                self._queue.task_done()
                break
            try:
                await self._process_task(task)
            finally:
                self._queue.task_done()

    async def _process_task(self, task: DownloadTask) -> None:
        await self._jobs.update_status(task.job_id, "processing")
        try:
            if task.media_kind == "vk_post_repost":
                text = await self._downloader.build_vk_post_repost_text(
                    task.url,
                    task.adapter,
                    task.auth_context,
                )
                await self._jobs.update_status(
                    task.job_id,
                    "done",
                    file_type="text",
                    file_size=None,
                    duration=None,
                    error_code=None,
                )
                await self._bot.send_message(task.chat_id, text)
                return

            result = await self._downloader.download(
                task.url,
                task.adapter,
                task.media_kind,
                task.auth_context,
            )
            await self._jobs.update_status(
                task.job_id,
                "done",
                file_type=result.media_type,
                file_size=result.size_bytes,
                duration=result.duration,
                error_code=None,
            )
            await self._send_media(task.chat_id, result.media_type, result.media_path, result.title)
        except AuthRequiredError:
            await self._jobs.update_status(task.job_id, "needs_auth", error_code="AUTH_REQUIRED")
            await self._bot.send_message(
                task.chat_id,
                "Контент закрыт. Нажмите «Повторить с авторизацией» и отправьте логин/пароль или токен.",
                reply_markup=auth_retry_keyboard(task.job_id),
            )
        except LimitError as exc:
            await self._jobs.update_status(task.job_id, "failed", error_code="LIMIT")
            await self._bot.send_message(task.chat_id, f"Не могу отправить: {exc}")
        except SourceUnsupportedError as exc:
            await self._jobs.update_status(task.job_id, "failed", error_code="UNSUPPORTED")
            await self._bot.send_message(task.chat_id, str(exc))
        except DependencyMissingError as exc:
            await self._jobs.update_status(task.job_id, "failed", error_code="DEPENDENCY_MISSING")
            await self._bot.send_message(task.chat_id, str(exc))
        except Exception:
            await self._jobs.update_status(task.job_id, "failed", error_code="DOWNLOAD_ERROR")
            await self._bot.send_message(
                task.chat_id,
                "Ошибка загрузки. Проверьте ссылку или попробуйте снова позже.",
            )

    async def _send_media(self, chat_id: int, media_type: str, media_path: Path, title: str) -> None:
        input_file = FSInputFile(media_path)
        if media_type == "audio":
            await self._bot.send_audio(chat_id=chat_id, audio=input_file, caption=title)
        elif media_type == "photo":
            await self._bot.send_photo(chat_id=chat_id, photo=input_file, caption=title)
        else:
            await self._bot.send_video(chat_id=chat_id, video=input_file, caption=title)
