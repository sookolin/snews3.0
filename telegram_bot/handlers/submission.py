"""User submission flow — /start, /suggest FSM: city → text → media → anonymity.

Users propose news which land in the admin panel (and moderation topic) with
status PENDING and origin USER.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select

from shared.database import session_scope
from shared.enums import MediaType, NewsOrigin
from shared.i18n import t
from shared.logging import get_logger
from shared.models.city import City
from shared.models.media import MediaAsset
from shared.models.news import News

router = Router(name="submission")
log = get_logger("bot.submission")

_LANG = "ru"

_EXT = {
    "photo": ".jpg",
    "video": ".mp4",
    "animation": ".mp4",
    "document": ".bin",
    "audio": ".mp3",
    "voice": ".ogg",
    "video_note": ".mp4",
}


async def _download_media(  # type: ignore[no-untyped-def]
    bot, file_id: str, media_type: str, news_id: int, position: int
) -> str | None:
    """Download a Telegram file to MEDIA_ROOT; return the relative path."""
    import os

    from shared.config import settings

    try:
        tg_file = await bot.get_file(file_id)
        rel_dir = os.path.join("news", str(news_id))
        abs_dir = os.path.join(settings.media_root, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)
        ext = os.path.splitext(tg_file.file_path or "")[1] or _EXT.get(media_type, ".bin")
        rel_path = os.path.join(rel_dir, f"{file_id[:16]}_{position}{ext}")
        abs_path = os.path.join(settings.media_root, rel_path)
        await bot.download_file(tg_file.file_path, destination=abs_path)
        return rel_path
    except Exception as exc:  # noqa: BLE001
        log.warning("bot_media_download_failed", file_id=file_id, error=str(exc))
        return None


class Submit(StatesGroup):
    choosing_city = State()
    entering_text = State()
    attaching_media = State()
    attaching_location = State()
    choosing_anonymity = State()
    entering_author = State()


@router.message(CommandStart(deep_link=True))
async def cmd_start_deeplink(message: Message, state: FSMContext) -> None:
    """Handle deep links like ``t.me/bot?start=suggest_5`` (city preselected)."""
    payload = (message.text or "").partition(" ")[2].strip()
    if payload.startswith("suggest_"):
        raw = payload.removeprefix("suggest_")
        if raw.isdigit():
            city_id = int(raw)
            async with session_scope() as session:
                city = await session.get(City, city_id)
            if city is not None and city.is_active:
                await state.clear()
                await state.update_data(city_id=city_id, media=[])
                await state.set_state(Submit.entering_text)
                await message.answer(
                    f"Город: <b>{city.name}</b>\n{t('bot.enter_text', _LANG)}",
                    parse_mode="HTML",
                )
                return
    if payload == "suggest":
        await cmd_suggest(message, state)
        return
    await message.answer(t("bot.start", _LANG))


async def _admin_keyboard(telegram_id: int):  # type: ignore[no-untyped-def]
    """Return a mini-app keyboard when the Telegram user is a linked admin.

    The admin panel is opened as a Telegram Web App, already associated with
    the account linked to this Telegram id. Telegram only accepts HTTPS URLs
    for web apps, so the button is omitted for local (http) setups.
    """
    from shared.config import settings
    from shared.enums import Permission
    from shared.security import user_has_permission
    from shared.services.user_service import UserService

    async with session_scope() as session:
        user = await UserService(session).get_by_telegram_id(telegram_id)
        if user is None or not user.is_active:
            return None
        if not user_has_permission(user, Permission.NEWS_VIEW):
            return None

    url = settings.admin_panel_url.rstrip("/")
    if not url.startswith("https://"):
        return None  # Telegram requires HTTPS for Web Apps

    from aiogram.types import (
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        WebAppInfo,
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🖥 Открыть админку",
                    web_app=WebAppInfo(url=f"{url}/news"),
                )
            ]
        ]
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Greeting; linked admins additionally get a mini-app button."""
    keyboard = None
    if message.from_user is not None:
        try:
            keyboard = await _admin_keyboard(message.from_user.id)
        except Exception as exc:  # noqa: BLE001
            log.warning("admin_keyboard_failed", error=str(exc))

    if keyboard is not None:
        await message.answer(
            f"{t('bot.start', _LANG)}\n\nВы вошли как администратор.",
            reply_markup=keyboard,
        )
        return
    await message.answer(t("bot.start", _LANG))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t("bot.cancelled", _LANG))


@router.message(Command("suggest"))
async def cmd_suggest(message: Message, state: FSMContext) -> None:
    """Start the submission flow by listing active cities."""
    async with session_scope() as session:
        cities = (
            await session.scalars(select(City).where(City.is_active.is_(True)).order_by(City.name))
        ).all()

    if not cities:
        await message.answer("Нет доступных городов.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=c.name, callback_data=f"sub_city:{c.id}")] for c in cities
        ]
    )
    await state.set_state(Submit.choosing_city)
    await message.answer(t("bot.choose_city", _LANG), reply_markup=keyboard)


@router.callback_query(Submit.choosing_city, F.data.startswith("sub_city:"))
async def chose_city(callback: CallbackQuery, state: FSMContext) -> None:
    city_id = int(callback.data.split(":", 1)[1])
    await state.update_data(city_id=city_id, media=[])
    await state.set_state(Submit.entering_text)
    await callback.message.answer(t("bot.enter_text", _LANG))
    await callback.answer()


@router.message(Submit.entering_text, F.text)
async def entered_text(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.text)
    await state.set_state(Submit.attaching_media)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("bot.done", _LANG), callback_data="sub_done")]
        ]
    )
    await message.answer(t("bot.attach_media", _LANG), reply_markup=keyboard)


@router.message(Submit.attaching_media)
async def attaching_media(message: Message, state: FSMContext) -> None:
    """Collect any attached media (photo/video/document/animation/audio/voice)."""
    data = await state.get_data()
    media: list[dict] = data.get("media", [])

    entry: dict | None = None
    if message.photo:
        entry = {"type": MediaType.PHOTO.value, "file_id": message.photo[-1].file_id}
    elif message.video:
        entry = {"type": MediaType.VIDEO.value, "file_id": message.video.file_id}
    elif message.animation:
        entry = {"type": MediaType.ANIMATION.value, "file_id": message.animation.file_id}
    elif message.document:
        entry = {"type": MediaType.DOCUMENT.value, "file_id": message.document.file_id}
    elif message.audio:
        entry = {"type": MediaType.AUDIO.value, "file_id": message.audio.file_id}
    elif message.voice:
        entry = {"type": MediaType.VOICE.value, "file_id": message.voice.file_id}
    elif message.video_note:
        entry = {"type": MediaType.VIDEO_NOTE.value, "file_id": message.video_note.file_id}

    if entry:
        media.append(entry)
        await state.update_data(media=media)
        await message.answer(f"Добавлено вложений: {len(media)}")
    else:
        await message.answer(t("bot.attach_media", _LANG))


@router.callback_query(Submit.attaching_media, F.data == "sub_done")
async def media_done(callback: CallbackQuery, state: FSMContext) -> None:
    """After media, ask for an optional geolocation."""
    await state.set_state(Submit.attaching_location)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="sub_geo_skip")]
        ]
    )
    await callback.message.answer(
        "Прикрепите геолокацию (кнопка «скрепка» → Геопозиция) или нажмите «Пропустить».",
        reply_markup=keyboard,
    )
    await callback.answer()


async def _ask_anonymity(message: Message, state: FSMContext) -> None:
    await state.set_state(Submit.choosing_anonymity)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("bot.yes", _LANG), callback_data="sub_anon:1"),
                InlineKeyboardButton(text=t("bot.no", _LANG), callback_data="sub_anon:0"),
            ]
        ]
    )
    await message.answer(t("bot.anonymous_q", _LANG), reply_markup=keyboard)


@router.message(Submit.attaching_location, F.location)
async def got_location(message: Message, state: FSMContext) -> None:
    loc = message.location
    venue = message.venue
    await state.update_data(
        latitude=loc.latitude,
        longitude=loc.longitude,
        location_title=(venue.title if venue else None),
        location_address=(venue.address if venue else None),
    )
    await message.answer("Геолокация добавлена.")
    await _ask_anonymity(message, state)


@router.callback_query(Submit.attaching_location, F.data == "sub_geo_skip")
async def skip_location(callback: CallbackQuery, state: FSMContext) -> None:
    await _ask_anonymity(callback.message, state)
    await callback.answer()


@router.callback_query(Submit.choosing_anonymity, F.data.startswith("sub_anon:"))
async def chose_anonymity(callback: CallbackQuery, state: FSMContext) -> None:
    anonymous = callback.data.split(":", 1)[1] == "1"
    await state.update_data(anonymous=anonymous)
    if anonymous:
        await _create_submission(callback.message, callback.from_user, state, author_name=None)
    else:
        await state.set_state(Submit.entering_author)
        await callback.message.answer("Укажите ваше имя и фамилию (будет показано как «Автор: …»):")
    await callback.answer()


@router.message(Submit.entering_author, F.text)
async def entered_author(message: Message, state: FSMContext) -> None:
    author = (message.text or "").strip()[:255] or None
    await _create_submission(message, message.from_user, state, author_name=author)


async def _create_submission(message, user, state: FSMContext, author_name: str | None) -> None:  # type: ignore[no-untyped-def]
    """Persist the submission (status PROCESSING) and enqueue AI + moderation."""
    from shared.enums import NewsStatus

    data = await state.get_data()
    anonymous = bool(data.get("anonymous"))
    await state.clear()

    async with session_scope() as session:
        news = News(
            original_text=data.get("text", ""),
            title=None,
            text=data.get("text", ""),
            status=NewsStatus.PROCESSING,
            origin=NewsOrigin.USER,
            city_id=data.get("city_id"),
            submitted_by_telegram_id=user.id,
            submitted_anonymously=anonymous,
            author_name=author_name,
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            location_title=data.get("location_title"),
            location_address=data.get("location_address"),
        )
        session.add(news)
        await session.flush()

        for position, item in enumerate(data.get("media", [])):
            rel_path = await _download_media(
                message.bot, item["file_id"], item["type"], news.id, position
            )
            session.add(
                MediaAsset(
                    news_id=news.id,
                    type=MediaType(item["type"]),
                    telegram_file_id=item["file_id"],
                    file_path=rel_path,
                    position=position,
                )
            )
        await session.commit()
        news_id = news.id

    # Run AI rewrite + send the moderation card via the worker queue.
    try:
        from workers.tasks import process_submission

        process_submission.delay(news_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("submission_enqueue_failed", news=news_id, error=str(exc))

    await message.answer(t("bot.submitted", _LANG))
