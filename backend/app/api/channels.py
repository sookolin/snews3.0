"""Telegram channel management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.deps import DBSession, require_permission
from shared.enums import Permission
from shared.models.channel import Channel
from shared.models.user import User
from shared.schemas.channel import ChannelCreate, ChannelOut, ChannelUpdate
from shared.schemas.common import Message, Page, PaginationParams
from shared.services.crud import CRUDService

router = APIRouter()


@router.get("", response_model=Page[ChannelOut])
async def list_channels(
    session: DBSession,
    params: PaginationParams = Depends(),
    city_id: int | None = None,
    _: User = Depends(require_permission(Permission.CHANNEL_MANAGE)),
) -> Page[ChannelOut]:
    filters = {"city_id": city_id} if city_id else None
    items, total = await CRUDService(session, Channel).list(
        params.offset, params.size, filters=filters
    )
    return Page.create([ChannelOut.model_validate(c) for c in items], total, params)


@router.post("", response_model=ChannelOut, status_code=201)
async def create_channel(
    payload: ChannelCreate,
    session: DBSession,
    _: User = Depends(require_permission(Permission.CHANNEL_MANAGE)),
) -> ChannelOut:
    obj = await CRUDService(session, Channel).create(payload)
    return ChannelOut.model_validate(obj)


@router.patch("/{channel_id}", response_model=ChannelOut)
async def update_channel(
    channel_id: int,
    payload: ChannelUpdate,
    session: DBSession,
    _: User = Depends(require_permission(Permission.CHANNEL_MANAGE)),
) -> ChannelOut:
    obj = await CRUDService(session, Channel).update(channel_id, payload)
    return ChannelOut.model_validate(obj)


@router.post("/{channel_id}/sync", response_model=ChannelOut)
async def sync_channel(
    channel_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.CHANNEL_MANAGE)),
) -> ChannelOut:
    """Pull the real title, @username and avatar from the Telegram channel.

    The bot must be a member/admin of the chat. Previews then show the actual
    channel identity instead of values typed by hand.
    """
    from shared.exceptions import ExternalServiceError
    from shared.services.telegram_admin import TelegramAdminService

    service = CRUDService(session, Channel)
    channel = await service.get_or_404(channel_id)
    raw = (channel.chat_id or "").strip()
    if raw.startswith("+") or "joinchat" in raw.lower():
        raise ExternalServiceError(
            "Ссылка-приглашение (+... или joinchat) не подходит как Chat ID. "
            "Для приватного канала укажите числовой ID вида -1001234567890 "
            "(бот должен быть админом канала)."
        )
    info = await TelegramAdminService().fetch_chat_info(channel.chat_id)
    if not info:
        hint = (
            "Проверьте, что бот добавлен в канал как администратор. "
            if raw.lstrip("-").isdigit() or raw.startswith("@")
            else "Указанный @username не найден — для приватного канала используйте "
                 "числовой Chat ID (например -1001234567890), у приватных каналов нет "
                 "публичного @username. "
        )
        raise ExternalServiceError(
            f"Не удалось прочитать канал. {hint}Проверьте chat_id и что бот добавлен в канал."
        )
    if info.get("title"):
        channel.title = info["title"]
    if info.get("username"):
        channel.username = info["username"]
    if info.get("avatar_url"):
        channel.avatar_url = info["avatar_url"]
    await session.flush()
    return ChannelOut.model_validate(channel)


@router.delete("/{channel_id}", response_model=Message)
async def delete_channel(
    channel_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.CHANNEL_MANAGE)),
) -> Message:
    await CRUDService(session, Channel).delete(channel_id)
    return Message(detail="Channel deleted")
