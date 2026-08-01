"""News endpoints: listing/filtering, editing, versioning, moderation, publish."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
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
    scope: str | None = Query(
        default=None,
        description="'world' → only world news, 'city' → only city news",
    ),
    search: str | None = Query(default=None, description="Full-text search"),
    _: User = Depends(require_permission(Permission.NEWS_VIEW)),
) -> Page[NewsListItem]:
    """List news with filtering and search."""
    stmt = select(News)
    count_stmt = select(func.count()).select_from(News)

    conditions = []
    if status:
        conditions.append(News.status == status)
    if scope == "world":
        conditions.append(News.is_world_news.is_(True))
    elif scope == "city":
        conditions.append(News.is_world_news.is_(False))
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
    await session.refresh(news)
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
        buttons=payload.buttons or [],
    )
    session.add(news)
    await session.flush()
    await session.refresh(news)
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

    # Editing content of an already published post marks it as "изменено" both
    # in the panel and on the moderation card.
    content_keys = {"title", "text", "emoji", "buttons", "source_name", "hide_source"}
    if news.published_message_ids and content_keys & set(data):
        news.is_edited = True
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

    # Keep Telegram in sync: update the published post and the moderation card.
    from shared.services.news_moderation import NewsModerationService

    service = NewsModerationService(session)
    if news.published_message_ids:
        await service.edit_published(news)
    if news.moderation_message_id:
        who = actor.full_name or actor.email
        await service.update_card(
            news,
            status_line=f"✏️ Изменено · {who}",
            keep_buttons=True,
        )
    await session.refresh(news)
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
    await session.refresh(news)
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

    # Record who processed it and when (moderator time, not AI time).
    news.processed_at = datetime.now(timezone.utc)

    slot = "—"
    if publish:
        if news.scheduled_at and news.scheduled_at > datetime.now(timezone.utc):
            news.status = NewsStatus.SCHEDULED
            slot = news.scheduled_at.strftime("%H:%M")
        else:
            # Queue with spacing so several approvals do not flood the channel.
            from workers.tasks import _schedule_publication

            slot = await _schedule_publication(session, news)
    await session.flush()

    # Reflect the decision on the moderation card and drop its buttons.
    from shared.services.news_moderation import NewsModerationService

    who = actor.full_name or actor.email
    queued = "" if slot in ("immediate", "—") else f" · в очереди на {slot}"
    await NewsModerationService(session).update_card(
        news, status_line=f"✅ Одобрено · {who}{queued}", keep_buttons=True
    )
    await session.refresh(news)
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
    # Reflect the decision on the moderation card and drop its buttons.
    from shared.services.news_moderation import NewsModerationService

    who = actor.full_name or actor.email
    await NewsModerationService(session).update_card(
        news, status_line=f"❌ Отклонено · {who}", keep_buttons=True
    )
    await session.refresh(news)
    return NewsOut.model_validate(news)


class BulkDeleteRequest(BaseModel):
    ids: list[int]


@router.post("/bulk-delete", response_model=Message)
async def bulk_delete_news(
    payload: BulkDeleteRequest,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.NEWS_DELETE)),
) -> Message:
    """Delete several news items at once."""
    from sqlalchemy import delete as sql_delete

    if not payload.ids:
        return Message(detail="Ничего не выбрано")
    await session.execute(sql_delete(News).where(News.id.in_(payload.ids)))
    await AuditService(session).log(
        "news.bulk_delete",
        user_id=actor.id,
        actor=actor.email,
        entity_type="news",
        changes={"ids": payload.ids},
        **meta,
    )
    return Message(detail=f"Удалено новостей: {len(payload.ids)}")


class RenderRequest(BaseModel):
    """Optional unsaved overrides so the preview matches the editor exactly."""

    template_id: int | None = None
    title: str | None = None
    text: str | None = None
    emoji: str | None = None
    author_name: str | None = None
    submitted_anonymously: bool | None = None
    source_name: str | None = None
    hide_source: bool | None = None


async def _load_global_tags(session) -> list[dict]:  # type: ignore[no-untyped-def]
    """Load global tags from settings, matching the publish path exactly.

    Preview render endpoints must feed the renderer the same ``global_tags`` the
    publisher does, otherwise ``{tag}`` placeholders (including premium tg-emoji)
    render empty in the editor preview and moderation card.
    """
    import json as _json

    from shared.services.settings_service import SettingsService

    try:
        raw = await SettingsService(session).get("templates.global_tags", "") or ""
        if isinstance(raw, str) and raw.strip().startswith("["):
            return _json.loads(raw)
        if isinstance(raw, list):
            return raw
    except Exception:  # noqa: BLE001 - preview must never fail over settings
        pass
    return []


@router.post("/{news_id}/render", response_model=Message)
async def render_news_preview(
    news_id: int,
    payload: RenderRequest,
    session: DBSession,
    _: User = Depends(require_permission(Permission.NEWS_VIEW)),
) -> Message:
    """Render the news through a template using unsaved editor values."""
    from shared.models.city import City
    from shared.models.source import Source
    from shared.services.template_renderer import TemplateRenderer

    news = await _get_news(session, news_id)
    template = await _resolve_template_for_news(session, news, payload.template_id)

    hide_source = (
        payload.hide_source if payload.hide_source is not None else news.hide_source
    )
    source_name = ""
    if not hide_source:
        source_name = payload.source_name if payload.source_name is not None else (
            news.source_name or ""
        )
        if not source_name and news.source_id:
            src = await session.get(Source, news.source_id)
            source_name = src.name if src else ""

    anonymous = (
        payload.submitted_anonymously
        if payload.submitted_anonymously is not None
        else news.submitted_anonymously
    )
    author = "" if anonymous else (
        payload.author_name if payload.author_name is not None else (news.author_name or "")
    )

    city_name = ""
    if news.city_id:
        city = await session.get(City, news.city_id)
        city_name = city.name if city else ""

    rendered = TemplateRenderer().render(
        template,
        title=(
            payload.title
            if payload.title is not None
            else (news.title or news.original_title or "")
        ),
        text=payload.text if payload.text is not None else (news.text or news.original_text or ""),
        source=source_name,
        source_url=news.original_url or "",
        city=city_name,
        author=author,
        emoji=payload.emoji if payload.emoji is not None else (news.emoji or ""),
        global_tags=await _load_global_tags(session),
    )
    return Message(detail=rendered)


async def _resolve_template_for_news(session, news, requested_id=None):  # type: ignore[no-untyped-def]
    """Pick the effective template for a news item, matching the publisher.

    Order of precedence:
      1. ``requested_id`` — an explicit choice from the editor dropdown;
      2. ``news.template_id`` — a template saved on the news itself;
      3. the news city's ``template_id`` — the template bound when the city was
         created (this is what "По умолчанию" must mean for a city's news);
      4. the global default template;
      5. any template at all.

    Previously the preview/editor endpoints skipped step 3 and jumped straight
    to the global default, so a city's own template was ignored in the editor
    even though the real publisher used it — the preview did not match the post.
    """
    from sqlalchemy import select as _select

    from shared.models.city import City
    from shared.models.template import Template

    # 1 + 2: explicit request, then a template pinned on the news.
    for candidate in (requested_id, getattr(news, "template_id", None)):
        if candidate:
            tpl = await session.get(Template, candidate)
            if tpl is not None:
                return tpl

    # 3: the city's own template (bound at city creation).
    if getattr(news, "city_id", None):
        city = await session.get(City, news.city_id)
        if city and city.template_id:
            tpl = await session.get(Template, city.template_id)
            if tpl is not None:
                return tpl

    # 4: global default, then 5: any template.
    tpl = await session.scalar(
        _select(Template).where(Template.is_default.is_(True)).limit(1)
    )
    if tpl is None:
        tpl = await session.scalar(_select(Template).limit(1))
    if tpl is None:
        raise NotFoundError("Нет доступного шаблона")
    return tpl


@router.get("/{news_id}/render", response_model=Message)
async def render_news(
    news_id: int,
    session: DBSession,
    template_id: int | None = None,
    _: User = Depends(require_permission(Permission.NEWS_VIEW)),
) -> Message:
    """Render the news through a template (for the live editor preview)."""
    from shared.models.source import Source
    from shared.services.template_renderer import TemplateRenderer

    news = await _get_news(session, news_id)
    template = await _resolve_template_for_news(session, news, template_id)

    source_name = ""
    if news.source_id:
        src = await session.get(Source, news.source_id)
        if src:
            source_name = src.name
    city_name = ""
    if news.city_id:
        from shared.models.city import City

        city = await session.get(City, news.city_id)
        city_name = city.name if city else ""
    author = "" if news.submitted_anonymously else (news.author_name or "")

    rendered = TemplateRenderer().render(
        template,
        title=news.title or news.original_title or "",
        text=news.text or news.original_text or "",
        source=source_name,
        source_url=news.original_url or "",
        city=city_name,
        author=author,
        emoji=news.emoji or "",
        global_tags=await _load_global_tags(session),
    )
    return Message(detail=rendered)


@router.post("/{news_id}/regenerate", response_model=NewsOut)
async def regenerate_news(
    news_id: int,
    session: DBSession,
    ai_profile_id: int | None = None,
    actor: User = Depends(require_permission(Permission.NEWS_EDIT)),
) -> NewsOut:
    """Re-run AI processing on the original text (for poor rewrites)."""
    from shared.services.ai_service import AIService

    news = await _get_news(session, news_id)
    await VersionService(session).snapshot(news, edited_by=actor.id, comment="before regenerate")
    try:
        result, profile = await AIService(session).process(
            news.original_title, news.original_text, ai_profile_id
        )
        news.title = result.title or news.original_title
        news.text = result.text or news.original_text
        news.ai_profile_id = profile.id
        if result.emoji:
            news.emoji = result.emoji
        if result.embedding:
            news.embedding = result.embedding
    except Exception as exc:  # noqa: BLE001
        from shared.exceptions import ExternalServiceError

        raise ExternalServiceError(f"AI: {exc}") from exc
    await session.flush()
    await session.refresh(news)
    return NewsOut.model_validate(news)


@router.post("/{news_id}/publish-all-cities", response_model=Message)
async def publish_all_cities(
    news_id: int,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.NEWS_PUBLISH)),
) -> Message:
    """Publish this single news item to the channels of every active city."""
    news = await _get_news(session, news_id)
    if news.published_message_ids:
        from shared.exceptions import ValidationError

        raise ValidationError("Новость уже опубликована — сначала снимите публикацию")

    from workers.tasks import publish_news_all_cities as task

    task.delay(news_id)
    await AuditService(session).log(
        "news.publish_all_cities",
        user_id=actor.id,
        actor=actor.email,
        entity_type="news",
        entity_id=news_id,
        **meta,
    )
    return Message(detail="Публикация во все каналы поставлена в очередь")


@router.post("/{news_id}/unpublish", response_model=NewsOut)
async def unpublish_news(
    news_id: int,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.NEWS_PUBLISH)),
) -> NewsOut:
    """Withdraw a published post: delete it from Telegram and restore buttons.

    After this the news can be edited and published again.
    """
    from shared.services.news_moderation import NewsModerationService

    news = await _get_news(session, news_id)
    service = NewsModerationService(session)
    removed = await service.delete_published(news)
    # WITHDRAWN records that the post *was* live and is now taken down; it can
    # be published again from the panel or the moderation card.
    news.status = NewsStatus.WITHDRAWN
    await session.flush()

    who = actor.full_name or actor.email
    await service.update_card(
        news,
        status_line=f"↩️ Публикация снята · {who} ({removed} сообщ.) — можно опубликовать заново",
        keep_buttons=True,
    )
    await AuditService(session).log(
        "news.unpublish",
        user_id=actor.id,
        actor=actor.email,
        entity_type="news",
        entity_id=news_id,
        changes={"removed": removed},
        **meta,
    )
    await session.refresh(news)
    return NewsOut.model_validate(news)


@router.post("/{news_id}/send-to-moderation", response_model=Message)
async def send_to_moderation(
    news_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.NEWS_MODERATE)),
) -> Message:
    """(Re)send the moderation card for this news to its city's Telegram topic."""
    news = await _get_news(session, news_id)
    if news.city_id is None:
        from shared.exceptions import ValidationError

        raise ValidationError("У новости не задан город")
    from workers.tasks import notify_moderation

    notify_moderation.delay(news_id)
    return Message(detail="Карточка отправлена в топик модерации")


@router.post("/{news_id}/publish", response_model=NewsOut)
async def publish_now(
    news_id: int,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.NEWS_PUBLISH)),
) -> NewsOut:
    """Publish the item immediately, bypassing the spacing queue.

    This endpoint is invoked from the editor's Publish button — an explicit
    manual action by a moderator. It always publishes right away and never
    places the item into the scheduled queue. Use ``/approve`` (from the
    moderation card) when queue-based spacing is desired.
    """
    news = await _get_news(session, news_id)
    if news.published_message_ids:
        from shared.exceptions import ValidationError

        raise ValidationError("Новость уже опубликована — сначала снимите публикацию")

    news.status = NewsStatus.APPROVED
    news.scheduled_at = None
    if news.moderated_by is None:
        news.moderated_by = actor.id
    if news.processed_at is None:
        news.processed_at = datetime.now(timezone.utc)
    await session.flush()

    from workers.tasks import publish_news as publish_task

    publish_task.delay(news.id)

    await AuditService(session).log(
        "news.publish",
        user_id=actor.id,
        actor=actor.email,
        entity_type="news",
        entity_id=news_id,
        changes={"slot": "immediate"},
        **meta,
    )
    await session.refresh(news)
    return NewsOut.model_validate(news)


class ScheduleRequest(BaseModel):
    """Publish the item at a specific moment (ISO datetime, UTC or with offset)."""

    scheduled_at: datetime | None = None


@router.post("/{news_id}/schedule", response_model=NewsOut)
async def schedule_news(
    news_id: int,
    payload: ScheduleRequest,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.NEWS_PUBLISH)),
) -> NewsOut:
    """Queue the item for publication at a given time (or cancel the schedule).

    The post is held by the platform and published by the scheduler worker at
    the requested moment. Telegram's own "scheduled messages" feature is not
    available to bots (Bot API has no scheduling parameter), so the delay is
    handled here and the post appears in the channel exactly at that time.
    """
    news = await _get_news(session, news_id)
    if news.published_message_ids:
        from shared.exceptions import ValidationError

        raise ValidationError("Новость уже опубликована — сначала снимите публикацию")

    if payload.scheduled_at is None:
        # Cancel the schedule and put the item back into moderation.
        news.scheduled_at = None
        if news.status == NewsStatus.SCHEDULED:
            news.status = NewsStatus.PENDING
        status_line = "🕒 Планирование отменено"
    else:
        when = payload.scheduled_at
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when <= datetime.now(timezone.utc):
            from shared.exceptions import ValidationError

            raise ValidationError("Время публикации должно быть в будущем")
        news.scheduled_at = when
        news.status = NewsStatus.SCHEDULED
        news.publish_immediately = False
        if news.moderated_by is None:
            news.moderated_by = actor.id
        if news.processed_at is None:
            news.processed_at = datetime.now(timezone.utc)

        from shared.services.settings_service import SettingsService

        tz_offset = int(
            await SettingsService(session).get("ui.timezone_offset_hours", 3)
        )
        local = when.astimezone(timezone(timedelta(hours=tz_offset)))
        status_line = f"🕒 Запланировано на {local.strftime('%d.%m.%Y %H:%M')}"
    await session.flush()

    from shared.services.news_moderation import NewsModerationService

    who = actor.full_name or actor.email
    await NewsModerationService(session).update_card(
        news, status_line=f"{status_line} · {who}", keep_buttons=True
    )
    await AuditService(session).log(
        "news.schedule",
        user_id=actor.id,
        actor=actor.email,
        entity_type="news",
        entity_id=news_id,
        changes={"scheduled_at": payload.scheduled_at.isoformat() if payload.scheduled_at else None},
        **meta,
    )
    await session.refresh(news)
    return NewsOut.model_validate(news)


@router.delete("/{news_id}", response_model=Message)
async def delete_news(
    news_id: int,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.NEWS_DELETE)),
) -> Message:
    news = await _get_news(session, news_id)

    # Remove the post from Telegram and mark the moderation card as deleted
    # before the row disappears.
    from shared.services.news_moderation import NewsModerationService

    service = NewsModerationService(session)
    removed = await service.delete_published(news)
    who = actor.full_name or actor.email
    await service.update_card(
        news, status_line=f"🗑 Удалено · {who}", keep_buttons=False
    )

    await session.delete(news)
    await session.flush()
    await AuditService(session).log(
        "news.delete",
        user_id=actor.id,
        actor=actor.email,
        entity_type="news",
        entity_id=news_id,
        changes={"telegram_messages_removed": removed},
        **meta,
    )
    return Message(detail="Новость удалена")


class CopyToCityPayload(BaseModel):
    city_id: int
    publish_immediately: bool = False


@router.post("/{news_id}/copy-to-city", response_model=NewsOut, status_code=201)
async def copy_news_to_city(
    news_id: int,
    payload: CopyToCityPayload,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.NEWS_PUBLISH)),
) -> NewsOut:
    """Clone a news item for another city, optionally publishing immediately."""
    original = await _get_news(session, news_id)

    news = News(
        original_title=original.original_title,
        original_text=original.original_text,
        original_url=original.original_url,
        title=original.title,
        text=original.text,
        emoji=original.emoji,
        city_id=payload.city_id,
        source_id=original.source_id,
        # Do NOT copy template_id: the publisher resolves the correct template
        # for the destination city. Carrying over the source city's template
        # would publish with the wrong design.
        template_id=None,
        origin=original.origin,
        status=NewsStatus.APPROVED if payload.publish_immediately else NewsStatus.PENDING,
        author_name=original.author_name,
        source_name=original.source_name,
        hide_source=original.hide_source,
        source_url_override=original.source_url_override,
        buttons=original.buttons or [],
        apply_watermark=original.apply_watermark,
        is_world_news=False,
        moderated_by=actor.id,
        processed_at=datetime.now(timezone.utc),
    )
    session.add(news)
    await session.flush()

    # Copy media attachments from the original.
    from shared.models.media import MediaAsset

    await session.refresh(original, attribute_names=["media"])
    for src_asset in original.media:
        new_asset = MediaAsset(
            news_id=news.id,
            type=src_asset.type,
            file_path=src_asset.file_path,
            processed_path=src_asset.processed_path,
            remote_url=src_asset.remote_url,
            telegram_file_id=src_asset.telegram_file_id,
            mime_type=src_asset.mime_type,
            file_size=src_asset.file_size,
            width=src_asset.width,
            height=src_asset.height,
            duration=src_asset.duration,
            caption=src_asset.caption,
            position=src_asset.position,
            is_spoiler=src_asset.is_spoiler,
            is_enabled=src_asset.is_enabled,
            thumbnail_path=src_asset.thumbnail_path,
        )
        session.add(new_asset)
    await session.flush()

    if payload.publish_immediately:
        from workers.tasks import publish_news as task
        task.delay(news.id)

    await AuditService(session).log(
        "news.copy_to_city",
        user_id=actor.id,
        actor=actor.email,
        entity_type="news",
        entity_id=news.id,
        changes={"copied_from": news_id, "city_id": payload.city_id, "publish_immediately": payload.publish_immediately},
        **meta,
    )
    await session.refresh(news)
    return NewsOut.model_validate(news)
