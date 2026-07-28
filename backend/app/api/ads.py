"""Advertisement management endpoints (+ publish + stats)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select

from backend.app.deps import DBSession, require_permission
from shared.enums import AdStatus, Permission
from shared.exceptions import NotFoundError
from shared.models.ad import Ad
from shared.models.user import User
from shared.schemas.ad import AdCreate, AdOut, AdStats, AdUpdate
from shared.schemas.common import Message, Page, PaginationParams
from shared.services.crud import CRUDService

router = APIRouter()

# Ads reuse the channel-management permission.
_PERM = Permission.CHANNEL_MANAGE


@router.get("/stats", response_model=AdStats)
async def ad_stats(
    session: DBSession,
    _: User = Depends(require_permission(Permission.MONITORING_VIEW)),
) -> AdStats:
    """Aggregate advertising statistics."""

    async def count(status: AdStatus | None = None) -> int:
        stmt = select(func.count()).select_from(Ad)
        if status:
            stmt = stmt.where(Ad.status == status)
        return await session.scalar(stmt) or 0

    total = await count()
    impressions = await session.scalar(select(func.coalesce(func.sum(Ad.impressions), 0))) or 0
    clicks = await session.scalar(select(func.coalesce(func.sum(Ad.clicks), 0))) or 0
    revenue = (
        await session.scalar(
            select(func.coalesce(func.sum(Ad.price), 0.0)).where(Ad.status == AdStatus.PUBLISHED)
        )
        or 0.0
    )
    ctr = (clicks / impressions * 100.0) if impressions else 0.0

    return AdStats(
        total=total,
        published=await count(AdStatus.PUBLISHED),
        draft=await count(AdStatus.DRAFT),
        scheduled=await count(AdStatus.SCHEDULED),
        total_impressions=int(impressions),
        total_clicks=int(clicks),
        total_revenue=float(revenue),
        ctr=round(ctr, 2),
    )


@router.get("", response_model=Page[AdOut])
async def list_ads(
    session: DBSession,
    params: PaginationParams = Depends(),
    status: AdStatus | None = None,
    _: User = Depends(require_permission(_PERM)),
) -> Page[AdOut]:
    filters = {"status": status} if status else None
    items, total = await CRUDService(session, Ad).list(params.offset, params.size, filters=filters)
    return Page.create([AdOut.model_validate(a) for a in items], total, params)


@router.post("", response_model=AdOut, status_code=201)
async def create_ad(
    payload: AdCreate,
    session: DBSession,
    _: User = Depends(require_permission(_PERM)),
) -> AdOut:
    obj = await CRUDService(session, Ad).create(payload)
    return AdOut.model_validate(obj)


@router.get("/{ad_id}", response_model=AdOut)
async def get_ad(
    ad_id: int,
    session: DBSession,
    _: User = Depends(require_permission(_PERM)),
) -> AdOut:
    obj = await CRUDService(session, Ad).get_or_404(ad_id)
    return AdOut.model_validate(obj)


@router.patch("/{ad_id}", response_model=AdOut)
async def update_ad(
    ad_id: int,
    payload: AdUpdate,
    session: DBSession,
    _: User = Depends(require_permission(_PERM)),
) -> AdOut:
    obj = await CRUDService(session, Ad).update(ad_id, payload)
    return AdOut.model_validate(obj)


@router.delete("/{ad_id}", response_model=Message)
async def delete_ad(
    ad_id: int,
    session: DBSession,
    _: User = Depends(require_permission(_PERM)),
) -> Message:
    await CRUDService(session, Ad).delete(ad_id)
    return Message(detail="Ad deleted")


class AdRenderRequest(BaseModel):
    """Unsaved ad values so the preview matches the final post exactly."""

    heading: str | None = None
    text: str | None = None
    advertiser: str | None = None
    advertiser_inn: str | None = None
    erid: str | None = None
    template_id: int | None = None


@router.post("/render", response_model=Message)
async def render_ad_preview(
    payload: AdRenderRequest,
    session: DBSession,
    _: User = Depends(require_permission(_PERM)),
) -> Message:
    """Render ad text through the chosen template + legal marking."""
    from shared.models.template import Template
    from shared.services.template_renderer import TemplateRenderer

    text = payload.text or ""
    if payload.template_id:
        template = await session.get(Template, payload.template_id)
        if template:
            text = TemplateRenderer().render(
                template,
                title=payload.heading or "",
                text=payload.text or "",
                source=payload.advertiser or "",
                city="",
            )
    elif payload.heading:
        text = f"<b>{payload.heading}</b>\n\n{text}"

    marking: list[str] = []
    if payload.advertiser:
        marking.append(f"Реклама. {payload.advertiser}")
    if payload.advertiser_inn:
        marking.append(f"ИНН {payload.advertiser_inn}")
    if payload.erid:
        marking.append(f"erid: {payload.erid}")
    if marking:
        text = f"{text}\n\n<i>{' · '.join(marking)}</i>"
    return Message(detail=text)


@router.get("/r/{ad_id}", include_in_schema=True)
async def track_click(ad_id: int, session: DBSession, to: str = ""):  # type: ignore[no-untyped-def]
    """Public click-tracking redirect.

    Telegram does not report clicks on inline URL buttons, so to measure them
    the button URL must point here; we increment the counter and then redirect
    the user to the real destination.

    Example button URL::

        https://your-domain/api/v1/ads/r/12?to=https%3A%2F%2Fadvertiser.example
    """
    from fastapi.responses import RedirectResponse

    ad = await session.get(Ad, ad_id)
    if ad is not None:
        ad.clicks = (ad.clicks or 0) + 1
        await session.flush()
    target = to or "https://t.me"
    return RedirectResponse(url=target, status_code=307)


@router.post("/{ad_id}/impression", response_model=Message)
async def register_impression(ad_id: int, session: DBSession) -> Message:
    """Register an impression (called by external counters/pixels)."""
    ad = await session.get(Ad, ad_id)
    if ad is None:
        raise NotFoundError(f"Ad {ad_id} not found")
    ad.impressions = (ad.impressions or 0) + 1
    await session.flush()
    return Message(detail="ok")


@router.post("/{ad_id}/media", response_model=AdOut)
async def upload_ad_media(
    ad_id: int,
    session: DBSession,
    file: UploadFile = File(...),
    _: User = Depends(require_permission(_PERM)),
) -> AdOut:
    """Attach an uploaded media file (from device) to an ad."""
    import os
    import uuid

    from shared.config import settings
    from shared.services.media_service import MediaService

    ad = await CRUDService(session, Ad).get_or_404(ad_id)
    contents = await file.read()
    subdir = os.path.join("ads", str(ad_id))
    os.makedirs(os.path.join(settings.media_root, subdir), exist_ok=True)
    ext = os.path.splitext(file.filename or "file")[1] or ".bin"
    rel_path = os.path.join(subdir, f"{uuid.uuid4().hex}{ext}")
    with open(os.path.join(settings.media_root, rel_path), "wb") as fh:
        fh.write(contents)
    mtype = MediaService.guess_type(file.content_type, file.filename or rel_path)
    files = list(ad.media_files or [])
    files.append({"path": rel_path, "type": mtype.value})
    ad.media_files = files
    await session.flush()
    await session.refresh(ad)
    return AdOut.model_validate(ad)


@router.post("/{ad_id}/publish", response_model=AdOut)
async def publish_ad(
    ad_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.NEWS_PUBLISH)),
) -> AdOut:
    """Publish an ad to its target channel (template, media, geo, erid marking)."""
    from shared.services.ad_publisher import AdPublisherService

    ad = await AdPublisherService(session).publish(ad_id)
    return AdOut.model_validate(ad)
