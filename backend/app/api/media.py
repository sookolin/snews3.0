"""Media endpoints: upload, update (caption/order/spoiler), delete, reorder."""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel

from backend.app.deps import DBSession, require_permission
from shared.config import settings
from shared.enums import Permission
from shared.exceptions import NotFoundError, ValidationError
from shared.models.media import MediaAsset
from shared.models.news import News
from shared.models.user import User
from shared.schemas.common import Message
from shared.schemas.media import MediaOut, MediaUpdate
from shared.services.crud import CRUDService
from shared.services.media_service import MediaService

router = APIRouter()


class ReorderRequest(BaseModel):
    ordered_ids: list[int]


class FromUrlRequest(BaseModel):
    news_id: int
    url: str
    caption: str | None = None


@router.post("/from-url", response_model=MediaOut, status_code=201)
async def add_media_from_url(
    payload: FromUrlRequest,
    session: DBSession,
    _: User = Depends(require_permission(Permission.NEWS_EDIT)),
) -> MediaOut:
    """Attach a remote media URL to a news item (used by manual compose)."""
    news = await session.get(News, payload.news_id)
    if news is None:
        raise NotFoundError(f"News {payload.news_id} not found")
    media_type = MediaService.guess_type(None, payload.url)
    position = len(news.media) if news.media else 0
    asset = MediaAsset(
        news_id=payload.news_id,
        type=media_type,
        remote_url=payload.url,
        caption=payload.caption,
        position=position,
    )
    session.add(asset)
    await session.flush()
    return MediaOut.model_validate(asset)


@router.post("/upload", response_model=MediaOut, status_code=201)
async def upload_media(
    session: DBSession,
    news_id: int = Form(...),
    file: UploadFile = File(...),
    caption: str | None = Form(default=None),
    _: User = Depends(require_permission(Permission.NEWS_EDIT)),
) -> MediaOut:
    """Attach an uploaded file to a news item."""
    news = await session.get(News, news_id)
    if news is None:
        raise NotFoundError(f"News {news_id} not found")

    contents = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise ValidationError(f"File exceeds {settings.max_upload_size_mb} MB limit")

    subdir = os.path.join("news", str(news_id))
    os.makedirs(os.path.join(settings.media_root, subdir), exist_ok=True)
    ext = os.path.splitext(file.filename or "file")[1] or ".bin"
    rel_path = os.path.join(subdir, f"{uuid.uuid4().hex}{ext}")
    with open(os.path.join(settings.media_root, rel_path), "wb") as fh:
        fh.write(contents)

    media_type = MediaService.guess_type(file.content_type, file.filename or rel_path)
    position = len(news.media) if news.media else 0
    asset = MediaAsset(
        news_id=news_id,
        type=media_type,
        file_path=rel_path,
        mime_type=file.content_type,
        file_size=len(contents),
        caption=caption,
        position=position,
    )
    session.add(asset)
    await session.flush()
    return MediaOut.model_validate(asset)


@router.patch("/{media_id}", response_model=MediaOut)
async def update_media(
    media_id: int,
    payload: MediaUpdate,
    session: DBSession,
    _: User = Depends(require_permission(Permission.NEWS_EDIT)),
) -> MediaOut:
    obj = await CRUDService(session, MediaAsset).update(media_id, payload)
    return MediaOut.model_validate(obj)


@router.post("/reorder", response_model=Message)
async def reorder_media(
    payload: ReorderRequest,
    session: DBSession,
    _: User = Depends(require_permission(Permission.NEWS_EDIT)),
) -> Message:
    """Set explicit ordering for a set of media assets."""
    for position, media_id in enumerate(payload.ordered_ids):
        asset = await session.get(MediaAsset, media_id)
        if asset:
            asset.position = position
    await session.flush()
    return Message(detail="Media reordered")


@router.delete("/{media_id}", response_model=Message)
async def delete_media(
    media_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.NEWS_EDIT)),
) -> Message:
    await CRUDService(session, MediaAsset).delete(media_id)
    return Message(detail="Media deleted")
