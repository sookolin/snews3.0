"""News endpoints: listing/filtering, editing, versioning, moderation, publish."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select

from backend.app.deps import ClientMeta, DBSession, require_permission
from shared.enums import NewsStatus, Permission
from shared.exceptions import NotFoundError
from shared.models.news import News
from shared.models.user import User
from shared.schemas.common import Message, Page, PaginationParams
from shared.schemas.news import (
    NewsCreate,
    NewsListItem,
    NewsOut,
    NewsUpdate,
    NewsVersionOut,
)
from shared.services.audit_service import AuditService
from shared.services.version_service import VersionService

router = APIRouter()


@router.get("", response_model=Page[NewsListItem])
async def list_news(
    session: DBSession,
    params: PaginationParams = Depends(),
    status: NewsStatus | None = None,
    city_id: int | None = None,
    source_id: int | None = None,
    origin: str | None = None,
    search: str | None = Query(default=None, description="Full-text search"),
    _: User = Depends(require_permission(Permission.NEWS_VIEW)),
) -> Page[NewsListItem]:
    """List news with filtering and search."""
    stmt = select(News)
    count_stmt = select(func.count()).select_from(News)

    conditions = []
    if status:
        conditions.append(News.status == status)
    if city_id:
        conditions.append(News.city_id == city_id)
    if source_id:
        conditions.append(News.source_id == source_id)
    if origin:
        conditions.append(News.origin == origin)
    if search:
        pattern = f"%{search}%"
        conditions.append(
            or_(
                News.title.ilike(pattern),
                News.original_title.ilike(pattern),
                News.text.ilike(pattern),
                News.original_text.ilike(pattern),
            )
        )
    for cond in conditions:
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = await session.scalar(count_stmt) or 0
    rows = (
        await session.scalars(
            stmt.order_by(News.created_at.desc()).offset(params.offset).limit(params.size)
        )
    ).all()
    return Page.create([NewsListItem.model_validate(n) for n in rows], total, params)


async def _get_news(session: DBSession, news_id: int) -> News:
    news = await session.get(News, news_id)
    if news is None:
        raise NotFoundError(f"News {news_id} not found")
    await session.refresh(news, attribute_names=["media"])
    return news


@router.post("", response_model=NewsOut, status_code=201)
async def create_news(
    payload: NewsCreate,
    session: DBSession,
    _: User = Depends(require_permission(Permission.NEWS_EDIT)),
) -> NewsOut:
    news = News(
        original_title=payload.original_title,
        original_text=payload.original_text,
        original_url=payload.original_url,
        title=payload.original_title,
        text=payload.original_text,
        city_id=payload.city_id,
        source_id=payload.source_id,
        origin=payload.origin,
        status=NewsStatus.PENDING,
        submitted_by_telegram_id=payload.submitted_by_telegram_id,
        submitted_anonymously=payload.submitted_anonymously,
        author_name=payload.author_name,
    )
    session.add(news)
    await session.flush()
    await session.refresh(news, attribute_names=["media"])
    return NewsOut.model_validate(news)


@router.get("/{news_id}", response_model=NewsOut)
async def get_news(
    news_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.NEWS_VIEW)),
) -> NewsOut:
    news = await _get_news(session, news_id)
    return NewsOut.model_validate(news)


@router.patch("/{news_id}", response_model=NewsOut)
async def update_news(
    news_id: int,
    payload: NewsUpdate,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.NEWS_EDIT)),
) -> NewsOut:
    """Edit a news item; snapshots the prior state for version history."""
    news = await _get_news(session, news_id)

    # Snapshot before applying changes.
    await VersionService(session).snapshot(news, edited_by=actor.id, comment=payload.edit_comment)

    data = payload.model_dump(exclude_unset=True, exclude={"edit_comment"})
    for key, value in data.items():
        setattr(news, key, value)
    await session.flush()

    await AuditService(session).log(
        "news.update",
        user_id=actor.id,
        actor=actor.email,
        entity_type="news",
        entity_id=news_id,
        changes=data,
        **meta,
    )
    await session.refresh(news, attribute_names=["media"])
    return NewsOut.model_validate(news)


@router.get("/{news_id}/versions", response_model=list[NewsVersionOut])
async def list_versions(
    news_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.NEWS_VIEW)),
) -> list[NewsVersionOut]:
    versions = await VersionService(session).list_versions(news_id)
    return [NewsVersionOut.model_validate(v) for v in versions]


@router.post("/{news_id}/versions/{version}/restore", response_model=NewsOut)
async def restore_version(
    news_id: int,
    version: int,
    session: DBSession,
    actor: User = Depends(require_permission(Permission.NEWS_EDIT)),
) -> NewsOut:
    news = await VersionService(session).restore(news_id, version, edited_by=actor.id)
    await session.refresh(news, attribute_names=["media"])
    return NewsOut.model_validate(news)


@router.post("/{news_id}/approve", response_model=NewsOut)
async def approve_news(
    news_id: int,
    session: DBSession,
    meta: ClientMeta,
    publish: bool = True,
    actor: User = Depends(require_permission(Permission.NEWS_MODERATE)),
) -> NewsOut:
    """Approve a news item and optionally enqueue publication."""
    news = await _get_news(session, news_id)
    news.status = NewsStatus.APPROVED
    news.moderated_by = actor.id
    await session.flush()

    await AuditService(session).log(
        "news.approve",
        user_id=actor.id,
        actor=actor.email,
        entity_type="news",
        entity_id=news_id,
        **meta,
    )

    if publish:
        if news.scheduled_at and news.scheduled_at > datetime.now(timezone.utc):
            news.status = NewsStatus.SCHEDULED
        else:
            from workers.tasks import publish_news

            publish_news.delay(news_id)
    await session.flush()
    await session.refresh(news, attribute_names=["media"])
    return NewsOut.model_validate(news)


@router.post("/{news_id}/reject", response_model=NewsOut)
async def reject_news(
    news_id: int,
    session: DBSession,
    meta: ClientMeta,
    reason: str | None = None,
    actor: User = Depends(require_permission(Permission.NEWS_MODERATE)),
) -> NewsOut:
    news = await _get_news(session, news_id)
    news.status = NewsStatus.REJECTED
    news.moderated_by = actor.id
    news.rejection_reason = reason
    await session.flush()
    await AuditService(session).log(
        "news.reject",
        user_id=actor.id,
        actor=actor.email,
        entity_type="news",
        entity_id=news_id,
        changes={"reason": reason},
        **meta,
    )
    await session.refresh(news, attribute_names=["media"])
    return NewsOut.model_validate(news)


@router.post("/{news_id}/publish", response_model=NewsOut)
async def publish_now(
    news_id: int,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.NEWS_PUBLISH)),
) -> NewsOut:
    """Publish immediately (synchronously) to the city's channels."""
    from shared.services.publisher_service import PublisherService

    news = await PublisherService(session).publish(news_id)
    await AuditService(session).log(
        "news.publish",
        user_id=actor.id,
        actor=actor.email,
        entity_type="news",
        entity_id=news_id,
        **meta,
    )
    await session.refresh(news, attribute_names=["media"])
    return NewsOut.model_validate(news)


@router.delete("/{news_id}", response_model=Message)
async def delete_news(
    news_id: int,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.NEWS_DELETE)),
) -> Message:
    news = await _get_news(session, news_id)
    await session.delete(news)
    await session.flush()
    await AuditService(session).log(
        "news.delete",
        user_id=actor.id,
        actor=actor.email,
        entity_type="news",
        entity_id=news_id,
        **meta,
    )
    return Message(detail="News deleted")
