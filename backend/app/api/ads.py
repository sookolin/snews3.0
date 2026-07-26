"""Advertisement management endpoints (+ publish + stats)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from backend.app.deps import DBSession, require_permission
from shared.enums import AdStatus, Permission
from shared.exceptions import NotFoundError, PublishError
from shared.models.ad import Ad
from shared.models.channel import Channel
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


@router.post("/{ad_id}/publish", response_model=AdOut)
async def publish_ad(
    ad_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.NEWS_PUBLISH)),
) -> AdOut:
    """Publish an ad to its target channel."""
    ad = await session.get(Ad, ad_id)
    if ad is None:
        raise NotFoundError(f"Ad {ad_id} not found")
    if ad.channel_id is None:
        raise PublishError("Ad has no target channel")
    channel = await session.get(Channel, ad.channel_id)
    if channel is None:
        raise PublishError("Target channel not found")

    from shared.enums import MediaType
    from shared.models.media import MediaAsset
    from shared.plugins.publishers import PublishRequest, publisher_registry

    # Build transient media assets from media_urls.
    media = [
        MediaAsset(
            id=-(i + 1),
            news_id=0,
            type=MediaType.PHOTO,
            remote_url=url,
            position=i,
            is_enabled=True,
            is_spoiler=False,
        )
        for i, url in enumerate(ad.media_urls or [])
    ]

    publisher = publisher_registry.get("telegram")(channel)
    result = await publisher.publish(
        PublishRequest(
            text=ad.text,
            media=media,
            is_spoiler=ad.is_spoiler,
            buttons=ad.buttons or [],
        )
    )
    if result.success:
        ad.status = AdStatus.PUBLISHED
        ad.published_at = datetime.now(timezone.utc)
        ad.published_message_ids = {channel.chat_id: result.message_ids}
        ad.error = None
    else:
        ad.status = AdStatus.FAILED
        ad.error = result.error
    await session.flush()
    await session.refresh(ad)
    if not result.success:
        raise PublishError(ad.error or "Ad publish failed")
    return AdOut.model_validate(ad)
