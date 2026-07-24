"""Watermark profile management endpoints (+ logo upload)."""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, UploadFile

from backend.app.deps import DBSession, require_permission
from shared.config import settings
from shared.enums import Permission
from shared.models.user import User
from shared.models.watermark import WatermarkProfile
from shared.schemas.common import Message, Page, PaginationParams
from shared.schemas.watermark import WatermarkCreate, WatermarkOut, WatermarkUpdate
from shared.services.crud import CRUDService

router = APIRouter()


@router.get("", response_model=Page[WatermarkOut])
async def list_watermarks(
    session: DBSession,
    params: PaginationParams = Depends(),
    _: User = Depends(require_permission(Permission.WATERMARK_MANAGE)),
) -> Page[WatermarkOut]:
    items, total = await CRUDService(session, WatermarkProfile).list(params.offset, params.size)
    return Page.create([WatermarkOut.model_validate(w) for w in items], total, params)


@router.post("", response_model=WatermarkOut, status_code=201)
async def create_watermark(
    payload: WatermarkCreate,
    session: DBSession,
    _: User = Depends(require_permission(Permission.WATERMARK_MANAGE)),
) -> WatermarkOut:
    service = CRUDService(session, WatermarkProfile)
    if payload.is_default:
        await service.clear_default()
    obj = await service.create(payload)
    return WatermarkOut.model_validate(obj)


@router.patch("/{watermark_id}", response_model=WatermarkOut)
async def update_watermark(
    watermark_id: int,
    payload: WatermarkUpdate,
    session: DBSession,
    _: User = Depends(require_permission(Permission.WATERMARK_MANAGE)),
) -> WatermarkOut:
    service = CRUDService(session, WatermarkProfile)
    if payload.is_default:
        await service.clear_default()
    obj = await service.update(watermark_id, payload)
    return WatermarkOut.model_validate(obj)


@router.delete("/{watermark_id}", response_model=Message)
async def delete_watermark(
    watermark_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.WATERMARK_MANAGE)),
) -> Message:
    await CRUDService(session, WatermarkProfile).delete(watermark_id)
    return Message(detail="Watermark deleted")


@router.post("/{watermark_id}/logo", response_model=WatermarkOut)
async def upload_logo(
    watermark_id: int,
    file: UploadFile,
    session: DBSession,
    _: User = Depends(require_permission(Permission.WATERMARK_MANAGE)),
) -> WatermarkOut:
    """Upload a logo image (PNG/SVG) for a watermark profile."""
    service = CRUDService(session, WatermarkProfile)
    obj = await service.get_or_404(watermark_id)

    logo_dir = os.path.join(settings.media_root, "watermarks")
    os.makedirs(logo_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "logo.png")[1] or ".png"
    path = os.path.join(logo_dir, f"{uuid.uuid4().hex}{ext}")
    with open(path, "wb") as fh:
        fh.write(await file.read())
    obj.logo_path = path
    await session.flush()
    return WatermarkOut.model_validate(obj)
