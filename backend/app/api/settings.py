"""Runtime settings + audit log endpoints."""

from __future__ import annotations

import pydantic
from fastapi import APIRouter, Depends
from sqlalchemy import select

from backend.app.deps import DBSession, require_permission
from shared.enums import Permission
from shared.models.audit import AuditLog
from shared.models.user import User
from shared.schemas.common import Page, PaginationParams
from shared.schemas.setting import SettingOut, SettingUpdate
from shared.services.settings_service import SettingsService

router = APIRouter()


@router.get("", response_model=dict)
async def get_all_settings(
    session: DBSession,
    prefix: str | None = None,
    _: User = Depends(require_permission(Permission.SETTINGS_MANAGE)),
) -> dict:
    """Return all runtime settings (optionally filtered by key prefix)."""
    return await SettingsService(session).get_many(prefix)


@router.put("/{key}", response_model=SettingOut)
async def set_setting(
    key: str,
    payload: SettingUpdate,
    session: DBSession,
    _: User = Depends(require_permission(Permission.SETTINGS_MANAGE)),
) -> SettingOut:
    """Create or update a runtime setting."""
    service = SettingsService(session)
    await service.set(
        key,
        payload.value,
        category=payload.category or "general",
        description=payload.description,
    )
    from shared.models.setting import Setting

    obj = await session.get(Setting, key)
    return SettingOut.model_validate(obj)


class WorldTopicCreate(pydantic.BaseModel):
    name: str = "🌍 Мировые новости"


@router.post("/world-topic", response_model=dict)
async def create_world_topic(
    payload: WorldTopicCreate,
    session: DBSession,
    _: User = Depends(require_permission(Permission.SETTINGS_MANAGE)),
) -> dict:
    """Create the dedicated moderation topic for world news (like a city topic).

    Stores the new thread id in ``telegram.world_topic_id`` so world news are
    routed there instead of a city topic.  If a city with ``is_world_bucket``
    exists its ``telegram_topic_id`` is updated to the same value so the
    cities page shows the correct ID without a manual refresh.
    """
    from sqlalchemy import select

    from shared.exceptions import ExternalServiceError
    from shared.models.city import City
    from shared.services.telegram_admin import TelegramAdminService

    topic_id = await TelegramAdminService().create_topic(payload.name)
    if topic_id is None:
        raise ExternalServiceError(
            "Не удалось создать топик. Проверьте, что группа модерации — форум "
            "и бот в ней администратор."
        )
    service = SettingsService(session)
    await service.set("telegram.world_topic_id", topic_id, category="telegram")

    # Also update the world-bucket city so its topic_id stays in sync.
    world_city = await session.scalar(
        select(City).where(City.is_world_bucket.is_(True)).limit(1)
    )
    if world_city is not None:
        world_city.telegram_topic_id = topic_id
    await session.commit()

    return {"topic_id": topic_id}


@router.get("/audit/logs", response_model=Page[dict])
async def audit_logs(
    session: DBSession,
    params: PaginationParams = Depends(),
    action: str | None = None,
    entity_type: str | None = None,
    _: User = Depends(require_permission(Permission.LOGS_VIEW)),
) -> Page[dict]:
    """Browse the audit log."""
    from sqlalchemy import func

    stmt = select(AuditLog)
    count_stmt = select(func.count()).select_from(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
        count_stmt = count_stmt.where(AuditLog.entity_type == entity_type)

    total = await session.scalar(count_stmt) or 0
    rows = (
        await session.scalars(
            stmt.order_by(AuditLog.created_at.desc()).offset(params.offset).limit(params.size)
        )
    ).all()
    items = [
        {
            "id": r.id,
            "action": r.action,
            "actor": r.actor,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "changes": r.changes,
            "ip_address": r.ip_address,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
    return Page.create(items, total, params)
