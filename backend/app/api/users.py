"""User management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.deps import ClientMeta, DBSession, require_permission
from shared.enums import Permission
from shared.models.user import User
from shared.schemas.common import Message, Page, PaginationParams
from shared.schemas.user import UserCreate, UserOut, UserUpdate
from shared.services.audit_service import AuditService
from shared.services.user_service import UserService

router = APIRouter()


PERMISSION_LABELS: dict[str, tuple[str, str]] = {
    "city:view": ("Просмотр городов", "Города"),
    "city:manage": ("Управление городами", "Города"),
    "source:view": ("Просмотр источников", "Источники"),
    "source:manage": ("Управление источниками", "Источники"),
    "news:view": ("Просмотр новостей", "Новости"),
    "news:edit": ("Редактирование новостей", "Новости"),
    "news:moderate": ("Модерация (одобрить/отклонить)", "Новости"),
    "news:publish": ("Публикация новостей", "Новости"),
    "news:delete": ("Удаление новостей", "Новости"),
    "template:manage": ("Управление шаблонами", "Оформление"),
    "watermark:manage": ("Управление водяным знаком", "Оформление"),
    "ai:manage": ("Настройка AI", "Оформление"),
    "settings:manage": ("Настройки системы", "Система"),
    "channel:manage": ("Каналы и реклама", "Публикация"),
    "user:view": ("Просмотр пользователей", "Пользователи"),
    "user:manage": ("Управление пользователями", "Пользователи"),
    "logs:view": ("Просмотр логов", "Система"),
    "backup:manage": ("Резервные копии", "Система"),
    "monitoring:view": ("Мониторинг", "Система"),
}


@router.get("/permissions", response_model=dict)
async def list_permissions(
    _: User = Depends(require_permission(Permission.USER_VIEW)),
) -> dict:
    """Catalog of all permissions plus the defaults granted by each role."""
    from shared.enums import ROLE_PERMISSIONS, UserRole

    catalog = [
        {
            "value": p.value,
            "label": PERMISSION_LABELS.get(p.value, (p.value, "Прочее"))[0],
            "group": PERMISSION_LABELS.get(p.value, (p.value, "Прочее"))[1],
        }
        for p in Permission
    ]
    roles = {
        role.value: sorted(perm.value for perm in perms)
        for role, perms in ROLE_PERMISSIONS.items()
    }
    return {"permissions": catalog, "roles": roles, "all_roles": [r.value for r in UserRole]}


@router.get("", response_model=Page[UserOut])
async def list_users(
    session: DBSession,
    params: PaginationParams = Depends(),
    _: User = Depends(require_permission(Permission.USER_VIEW)),
) -> Page[UserOut]:
    users, total = await UserService(session).list(params.offset, params.size)
    return Page.create([UserOut.model_validate(u) for u in users], total, params)


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreate,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.USER_MANAGE)),
) -> UserOut:
    user = await UserService(session).create(payload)
    await AuditService(session).log(
        "user.create",
        user_id=actor.id,
        actor=actor.email,
        entity_type="user",
        entity_id=user.id,
        **meta,
    )
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    session: DBSession,
    _: User = Depends(require_permission(Permission.USER_VIEW)),
) -> UserOut:
    user = await UserService(session).get_or_404(user_id)
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.USER_MANAGE)),
) -> UserOut:
    user = await UserService(session).update(user_id, payload)
    await AuditService(session).log(
        "user.update",
        user_id=actor.id,
        actor=actor.email,
        entity_type="user",
        entity_id=user_id,
        changes=payload.model_dump(exclude_unset=True, exclude={"password"}),
        **meta,
    )
    return UserOut.model_validate(user)


@router.delete("/{user_id}", response_model=Message)
async def delete_user(
    user_id: int,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.USER_MANAGE)),
) -> Message:
    await UserService(session).delete(user_id)
    await AuditService(session).log(
        "user.delete",
        user_id=actor.id,
        actor=actor.email,
        entity_type="user",
        entity_id=user_id,
        **meta,
    )
    return Message(detail="User deleted")
