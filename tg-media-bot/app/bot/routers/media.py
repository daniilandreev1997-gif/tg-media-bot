from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bot.callbacks import AuthRetryCallback, MediaChoiceCallback
from app.bot.context import AppContext
from app.bot.keyboards import media_choice_keyboard
from app.services.downloader import AuthRequiredError, DependencyMissingError
from app.services.queue import DownloadTask
from app.services.source_adapters import detect_source, is_tiktok_photo_url, is_vk_wall_post_url
from app.services.types import AuthContext

router = Router(name="media")


class AuthStates(StatesGroup):
    waiting_credentials = State()


def _user_id(message: Message | CallbackQuery) -> int | None:
    user = message.from_user
    if user is None:
        return None
    return user.id


@router.message(F.text)
async def url_message_handler(message: Message, app_ctx: AppContext) -> None:
    text = (message.text or "").strip()
    user_tg_id = _user_id(message)
    if user_tg_id is None:
        return

    user_id = await app_ctx.users.get_or_create(user_tg_id)
    adapter = detect_source(text)
    if adapter is None:
        return

    await message.answer("Ссылка принята, обрабатываю...")

    if adapter.name == "vk" and is_vk_wall_post_url(text):
        credential = await app_ctx.credentials.get(user_id, adapter.provider)
        auth_context = None
        if credential is not None:
            auth_context = AuthContext(
                login=credential.login,
                password_or_token=credential.password_or_token,
            )
        job_id = await app_ctx.jobs.create(user_id=user_id, url=text, source="vk_post", status="queued")
        await app_ctx.queue.enqueue(
            DownloadTask(
                job_id=job_id,
                chat_id=message.chat.id,
                url=text,
                adapter=adapter,
                media_kind="vk_post_repost",
                auth_context=auth_context,
            )
        )
        await message.answer("Делаю репост поста VK. Это может занять немного времени.")
        return
    if adapter.name == "tiktok" and is_tiktok_photo_url(text):
        job_id = await app_ctx.jobs.create(user_id=user_id, url=text, source="tiktok_photo", status="queued")
        await app_ctx.queue.enqueue(
            DownloadTask(
                job_id=job_id,
                chat_id=message.chat.id,
                url=text,
                adapter=adapter,
                media_kind="tiktok_photo",
            )
        )
        await message.answer("Распознал фото-пост TikTok. Сейчас отправлю фото.")
        return

    try:
        info = await app_ctx.downloader.inspect(text, adapter)
    except AuthRequiredError:
        job_id = await app_ctx.jobs.create(user_id=user_id, url=text, source=adapter.name, status="needs_auth")
        await message.answer(
            "Для этой ссылки нужна авторизация. Нажмите кнопку ниже.",
            reply_markup=media_choice_keyboard(job_id=job_id, has_video=adapter.can_video, has_audio=adapter.can_audio),
        )
        return
    except DependencyMissingError as exc:
        await message.answer(str(exc))
        return
    except Exception:
        await message.answer("Не удалось обработать ссылку. Проверьте формат и попробуйте еще раз.")
        return

    if info.duration is not None and info.duration > app_ctx.settings.max_duration_min * 60:
        await message.answer(f"Слишком длинное видео. Лимит: {app_ctx.settings.max_duration_min} мин.")
        return

    job_id = await app_ctx.jobs.create(user_id=user_id, url=text, source=adapter.name, status="ready")
    kb = media_choice_keyboard(job_id=job_id, has_video=info.has_video, has_audio=info.has_audio)
    await message.answer(
        f"Найдено: {info.title}\nВыберите формат:",
        reply_markup=kb,
    )


@router.callback_query(MediaChoiceCallback.filter())
async def media_choice_handler(
    call: CallbackQuery,
    callback_data: MediaChoiceCallback,
    app_ctx: AppContext,
) -> None:
    if call.message is None:
        await call.answer()
        return
    if callback_data.kind not in {"video", "audio"}:
        await call.answer("Неизвестный формат")
        return

    job = await app_ctx.jobs.get(callback_data.job_id)
    if job is None:
        await call.answer("Задача не найдена", show_alert=True)
        return

    adapter = detect_source(job["url"])
    if adapter is None:
        await call.answer("Источник не поддерживается", show_alert=True)
        return

    credential = await app_ctx.credentials.get(int(job["user_id"]), adapter.provider)
    auth_context = None
    if credential is not None:
        auth_context = AuthContext(
            login=credential.login,
            password_or_token=credential.password_or_token,
        )

    await app_ctx.jobs.update_status(callback_data.job_id, "queued")
    await app_ctx.queue.enqueue(
        DownloadTask(
            job_id=callback_data.job_id,
            chat_id=call.message.chat.id,
            url=job["url"],
            adapter=adapter,
            media_kind=callback_data.kind,
            auth_context=auth_context,
        )
    )
    await call.answer("Поставил в очередь")
    await call.message.answer("Запрос отправлен в очередь, скоро пришлю файл.")


@router.callback_query(AuthRetryCallback.filter(F.action == "retry"))
async def auth_retry_handler(
    call: CallbackQuery,
    callback_data: AuthRetryCallback,
    state: FSMContext,
    app_ctx: AppContext,
) -> None:
    if call.message is None:
        await call.answer()
        return

    job = await app_ctx.jobs.get(callback_data.job_id)
    if job is None:
        await call.answer("Задача не найдена", show_alert=True)
        return

    adapter = detect_source(job["url"])
    if adapter is None:
        await call.answer("Источник не поддерживается", show_alert=True)
        return

    await state.set_state(AuthStates.waiting_credentials)
    await state.update_data(job_id=callback_data.job_id, provider=adapter.provider)
    await call.answer()
    await call.message.answer(
        "Отправьте данные в формате:\n"
        "логин:пароль\n"
        "или только токен (одной строкой)."
    )


@router.message(AuthStates.waiting_credentials, F.text)
async def credentials_handler(message: Message, state: FSMContext, app_ctx: AppContext) -> None:
    user_tg_id = _user_id(message)
    if user_tg_id is None:
        await state.clear()
        return
    payload = await state.get_data()
    job_id = payload.get("job_id")
    provider = payload.get("provider")
    if not isinstance(job_id, int) or not isinstance(provider, str):
        await message.answer("Сессия истекла. Запустите авторизацию заново.")
        await state.clear()
        return

    user_id = await app_ctx.users.get_or_create(user_tg_id)
    raw = (message.text or "").strip()
    login: str | None = None
    secret = raw
    if ":" in raw:
        login, secret = raw.split(":", 1)
        login = login.strip() or None
        secret = secret.strip()

    if not secret:
        await message.answer("Не удалось распознать данные. Повторите отправку.")
        return

    await app_ctx.credentials.save(user_id=user_id, provider=provider, login=login, password_or_token=secret)
    await state.clear()

    job = await app_ctx.jobs.get(job_id)
    if job is None:
        await message.answer("Задача не найдена. Пришлите ссылку заново.")
        return

    adapter = detect_source(job["url"])
    if adapter is None:
        await message.answer("Источник больше не поддерживается.")
        return

    media_kind = "audio" if not adapter.can_video else "video"
    if job.get("source") == "vk_post":
        media_kind = "vk_post_repost"
    elif job.get("source") == "tiktok_photo":
        media_kind = "tiktok_photo"
    await app_ctx.jobs.update_status(job_id, "queued")
    await app_ctx.queue.enqueue(
        DownloadTask(
            job_id=job_id,
            chat_id=message.chat.id,
            url=job["url"],
            adapter=adapter,
            media_kind=media_kind,
            auth_context=AuthContext(login=login, password_or_token=secret),
        )
    )
    await message.answer("Данные сохранены. Повторяю загрузку.")
