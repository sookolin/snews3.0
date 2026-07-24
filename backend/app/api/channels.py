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


@router.delete("/{channel_id}", response_model=Message)
async def delete_channel(
    channel_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.CHANNEL_MANAGE)),
) -> Message:
    await CRUDService(session, Channel).delete(channel_id)
    return Message(detail="Channel deleted")
