"""User management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.deps import ClientMeta, CurrentUser, DBSession, require_permission
from shared.enums import Permission, UserRole
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


#: Permissions whose access can be scoped to specific cities in Права ролей.
CITY_SCOPABLE_PERMISSION_VALUES: set[str] = {
    "city:view", "city:manage",
    "source:view", "source:manage",
    "news:view", "news:edit", "news:moderate", "news:publish", "news:delete",
}


@router.get("/permissions", response_model=dict)
async def list_permissions(
    session: DBSession,
    _: User = Depends(require_permission(Permission.USER_VIEW)),
) -> dict:
    """Catalog of all permissions plus the defaults granted by each role.

    ``all_roles`` includes both the built-in roles and any custom roles
    created via "Права ролей" (persisted in the ``roles.custom`` setting).
    """
    from shared.enums import ROLE_PERMISSIONS, UserRole
    from shared.services.settings_service import SettingsService

    catalog = [
        {
            "value": p.value,
            "label": PERMISSION_LABELS.get(p.value, (p.value, "Прочее"))[0],
            "group": PERMISSION_LABELS.get(p.value, (p.value, "Прочее"))[1],
            "city_scoped": p.value in CITY_SCOPABLE_PERMISSION_VALUES,
        }
        for p in Permission
    ]
    roles = {
        role.value: sorted(perm.value for perm in perms)
        for role, perms in ROLE_PERMISSIONS.items()
    }
    custom_roles = await SettingsService(session).get("roles.custom", []) or []
    deleted_builtin = set(await SettingsService(session).get("roles.deleted_builtin", []) or [])
    all_roles = [r.value for r in UserRole if r.value not in deleted_builtin] + [
        r for r in custom_roles if r not in {rr.value for rr in UserRole}
    ]
    for role in custom_roles:
        roles.setdefault(role, [])
    for role in deleted_builtin:
        roles.pop(role, None)
    return {"permissions": catalog, "roles": roles, "all_roles": all_roles}


@router.post("/roles", response_model=dict, status_code=201)
async def create_role(
    payload: dict,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.USER_MANAGE)),
) -> dict:
    """Create a new custom role with no permissions by default.

    Payload: ``{"key": "curator", "label": "Куратор", "color": "#..."}``.
    ``key`` must be unique and lowercase-slug-like; permissions are then
    configured in Права ролей like any other role.
    """
    import re

    from shared.enums import UserRole
    from shared.services.settings_service import SettingsService

    key = str(payload.get("key") or "").strip().lower()
    label = str(payload.get("label") or key).strip()
    color = str(payload.get("color") or "").strip()
    if not key or not re.fullmatch(r"[a-z][a-z0-9_]{1,31}", key):
        from shared.exceptions import ValidationError

        raise ValidationError(
            "Ключ роли: латиница в нижнем регистре, цифры и _, 2-32 символа"
        )
    if key in {r.value for r in UserRole}:
        from shared.exceptions import ConflictError

        raise ConflictError("Такой ключ роли зарезервирован системой")

    settings_service = SettingsService(session)
    custom_roles: list[str] = list(await settings_service.get("roles.custom", []) or [])
    if key in custom_roles:
        from shared.exceptions import ConflictError

        raise ConflictError("Роль с таким ключом уже существует")
    custom_roles.append(key)
    await settings_service.set("roles.custom", custom_roles, category="ui")

    if label:
        labels = dict(await settings_service.get("roles.labels", {}) or {})
        labels[key] = label
        await settings_service.set("roles.labels", labels, category="ui")
    if color:
        colors = dict(await settings_service.get("roles.colors", {}) or {})
        colors[key] = color
        await settings_service.set("roles.colors", colors, category="ui")

    # Start with an explicit empty permission set so the role grants nothing
    # until configured in Права ролей.
    role_perms = dict(await settings_service.get("roles.permissions", {}) or {})
    role_perms.setdefault(key, {"grant": [], "deny": [], "city_scoped": {}})
    await settings_service.set("roles.permissions", role_perms, category="ui")

    await AuditService(session).log(
        "role.create",
        user_id=actor.id,
        actor=actor.email,
        entity_type="role",
        entity_id=key,
        changes={"label": label, "color": color},
        **meta,
    )
    return {"key": key, "label": label or key, "color": color}


@router.delete("/roles/{role_key}", response_model=Message)
async def delete_role(
    role_key: str,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.USER_MANAGE)),
) -> Message:
    """Delete a role — custom or built-in (except ``super_admin``).

    Users currently on this role are NOT auto-migrated; they keep the role
    string until an admin re-assigns them. To avoid silently leaving those
    accounts with the role's original permission set, the role's effective
    permissions are also zeroed out (denied) so it grants nothing going
    forward, exactly like a freshly-created custom role. Built-in roles are
    additionally hidden from the "all_roles" catalog (``roles.deleted_builtin``)
    so they no longer appear in role pickers; ``super_admin`` can never be
    removed because at least one fully-privileged role must always exist.
    """
    from shared.enums import Permission as P
    from shared.enums import UserRole
    from shared.exceptions import ValidationError
    from shared.services.settings_service import SettingsService

    if role_key == UserRole.SUPER_ADMIN.value:
        raise ValidationError("Роль «Супер-админ» удалить нельзя")

    settings_service = SettingsService(session)
    is_builtin = role_key in {r.value for r in UserRole}

    if is_builtin:
        deleted_builtin: list[str] = list(
            await settings_service.get("roles.deleted_builtin", []) or []
        )
        if role_key not in deleted_builtin:
            deleted_builtin.append(role_key)
        await settings_service.set("roles.deleted_builtin", deleted_builtin, category="ui")
    else:
        custom_roles: list[str] = list(await settings_service.get("roles.custom", []) or [])
        if role_key not in custom_roles:
            from shared.exceptions import NotFoundError

            raise NotFoundError("Роль не найдена")
        custom_roles.remove(role_key)
        await settings_service.set("roles.custom", custom_roles, category="ui")

    # Zero out effective permissions so existing users on this role
    # immediately lose all access from it, instead of silently keeping the
    # built-in default permission set.
    role_perms = dict(await settings_service.get("roles.permissions", {}) or {})
    if is_builtin:
        role_perms[role_key] = {"grant": [], "deny": [p.value for p in P], "city_scoped": {}}
    else:
        role_perms.pop(role_key, None)
    await settings_service.set("roles.permissions", role_perms, category="ui")

    labels = dict(await settings_service.get("roles.labels", {}) or {})
    labels.pop(role_key, None)
    await settings_service.set("roles.labels", labels, category="ui")

    colors = dict(await settings_service.get("roles.colors", {}) or {})
    colors.pop(role_key, None)
    await settings_service.set("roles.colors", colors, category="ui")

    await AuditService(session).log(
        "role.delete",
        user_id=actor.id,
        actor=actor.email,
        entity_type="role",
        entity_id=role_key,
        **meta,
    )
    return Message(detail="Роль удалена")


#: Built-in role names, used when no custom label was set.
DEFAULT_ROLE_LABELS: dict[str, str] = {
    "super_admin": "Супер-админ",
    "admin": "Администратор",
    "moderator": "Модератор",
    "editor": "Редактор",
    "reviewer": "Наблюдатель",
}


@router.get("/role-labels", response_model=dict)
async def get_role_labels(session: DBSession, _: CurrentUser) -> dict:
    """Display names of the roles (renamed ones override the defaults).

    Available to any authenticated user because every page renders role tags.
    """
    from shared.services.settings_service import SettingsService

    custom = await SettingsService(session).get("roles.labels", {}) or {}
    return {**DEFAULT_ROLE_LABELS, **{k: v for k, v in custom.items() if v}}


@router.put("/role-labels", response_model=dict)
async def set_role_labels(
    payload: dict,
    session: DBSession,
    _: User = Depends(require_permission(Permission.USER_MANAGE)),
) -> dict:
    """Rename roles. Keys are role values, values are the new display names."""
    from shared.services.settings_service import SettingsService

    labels = {
        key: str(value).strip()
        for key, value in (payload or {}).items()
        if key in DEFAULT_ROLE_LABELS and str(value or "").strip()
    }
    await SettingsService(session).set("roles.labels", labels, category="ui")
    return {**DEFAULT_ROLE_LABELS, **labels}


@router.get("/role-colors", response_model=dict)
async def get_role_colors(session: DBSession, _: CurrentUser) -> dict:
    """Role colors (hex codes). Available to all authenticated users."""
    from shared.services.settings_service import SettingsService

    colors = await SettingsService(session).get("roles.colors", {}) or {}
    return {k: v for k, v in colors.items() if v}


@router.put("/role-colors", response_model=dict)
async def set_role_colors(
    payload: dict,
    session: DBSession,
    _: User = Depends(require_permission(Permission.USER_MANAGE)),
) -> dict:
    """Set role colors. Keys are role values, values are hex color codes."""
    from shared.services.settings_service import SettingsService

    colors = {
        key: str(value).strip()
        for key, value in (payload or {}).items()
        if key in DEFAULT_ROLE_LABELS and str(value or "").strip()
    }
    await SettingsService(session).set("roles.colors", colors, category="ui")
    return colors


@router.get("/role-permissions", response_model=dict)
async def get_role_permissions(
    session: DBSession,
    _: User = Depends(require_permission(Permission.USER_VIEW)),
) -> dict:
    """Return custom per-role permission overrides (grant / deny per role).

    Format: {"admin": {"grant": [...], "deny": [...]}, ...}
    """
    from shared.services.settings_service import SettingsService

    overrides = await SettingsService(session).get("roles.permissions", {}) or {}
    return overrides


@router.put("/role-permissions", response_model=dict)
async def set_role_permissions(
    payload: dict,
    session: DBSession,
    _: User = Depends(require_permission(Permission.USER_MANAGE)),
) -> dict:
    """Persist per-role permission overrides, including per-city scoping.

    Payload per role::

        {
          "admin": {
            "grant": ["news:delete"],
            "deny": [],
            "city_scoped": {
              "news:moderate": {"mode": "grant_selected", "cities": [1, 2]},
              "source:manage": {"mode": "deny"},
            },
          },
          ...
        }

    ``city_scoped`` modes, for permissions in ``CITY_SCOPABLE_PERMISSION_VALUES``:
      - ``role`` — use the role's built-in default (unrestricted if granted).
      - ``grant`` — allow for every city.
      - ``grant_selected`` — allow only for ``cities``.
      - ``deny`` — deny for every city (permission unusable).
      - ``deny_selected`` — allow everywhere EXCEPT ``cities``.

    An "edit"-style permission (moderate/publish/delete/manage) is further
    intersected with the matching "view" permission's city scope at
    resolution time — you cannot act on a city you cannot see (enforced in
    ``shared.security.user_city_access``, not stored here).

    Super admin role is immutable and always gets all permissions.
    """
    from shared.services.settings_service import SettingsService
    from shared.enums import UserRole, Permission as P

    settings_service = SettingsService(session)
    custom_roles: list[str] = list(await settings_service.get("roles.custom", []) or [])
    allowed_roles = ({r.value for r in UserRole} | set(custom_roles)) - {"super_admin"}
    allowed_perms = {p.value for p in P}
    allowed_modes = {"role", "grant", "grant_selected", "deny", "deny_selected"}

    cleaned: dict = {}
    for role, overrides in (payload or {}).items():
        if role not in allowed_roles:
            continue
        grant = [p for p in (overrides.get("grant") or []) if p in allowed_perms]
        deny = [p for p in (overrides.get("deny") or []) if p in allowed_perms]

        city_scoped_in = overrides.get("city_scoped") or {}
        city_scoped: dict = {}
        for perm, scope in city_scoped_in.items():
            if perm not in CITY_SCOPABLE_PERMISSION_VALUES or not isinstance(scope, dict):
                continue
            mode = scope.get("mode")
            if mode not in allowed_modes:
                continue
            cities = [int(c) for c in (scope.get("cities") or []) if isinstance(c, (int, str))]
            city_scoped[perm] = {"mode": mode, "cities": cities}

        cleaned[role] = {"grant": grant, "deny": deny, "city_scoped": city_scoped}
    await settings_service.set("roles.permissions", cleaned, category="ui")
    return cleaned


@router.get("", response_model=Page[UserOut])
async def list_users(
    session: DBSession,
    actor: User = Depends(require_permission(Permission.USER_VIEW)),
    params: PaginationParams = Depends(),
) -> Page[UserOut]:
    users, total = await UserService(session).list(params.offset, params.size)
    # Super admins are only visible to other super admins.
    if actor.role != UserRole.SUPER_ADMIN:
        users = [u for u in users if u.role != UserRole.SUPER_ADMIN]
        total = len(users)
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
    # Snapshot fields we watch before the update.
    target_before = await UserService(session).get_or_404(user_id)
    old_role = target_before.role
    old_active = target_before.is_active
    old_full_name = target_before.full_name
    old_email = target_before.email
    old_telegram_id = target_before.telegram_id
    old_telegram_username = target_before.telegram_username

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

    # Create in-app notifications for significant account changes.
    from shared.models.notification import Notification
    from datetime import datetime, timezone

    changes = payload.model_dump(exclude_unset=True)
    notifications: list[Notification] = []

    FIELD_LABELS = {
        "full_name": "имя",
        "email": "email",
        "telegram_id": "Telegram ID",
        "telegram_username": "Telegram ник",
    }

    if "role" in changes and changes["role"] != old_role:
        old_key = old_role.value if hasattr(old_role, "value") else str(old_role)
        new_role = changes["role"]
        new_key = new_role.value if hasattr(new_role, "value") else str(new_role)
        notifications.append(
            Notification(
                user_id=user_id,
                type="role_changed",
                title="Ваша роль изменена",
                body=f"Роль изменена с «{old_key}» на «{new_key}»",
                url="/profile",
                is_read=False,
                created_at=datetime.now(timezone.utc),
            )
        )

    if "is_active" in changes and changes["is_active"] != old_active:
        if not changes["is_active"]:
            notifications.append(
                Notification(
                    user_id=user_id,
                    type="account_deactivated",
                    title="Ваш аккаунт деактивирован",
                    body="Администратор деактивировал ваш аккаунт.",
                    url=None,
                    is_read=False,
                    created_at=datetime.now(timezone.utc),
                )
            )
        else:
            notifications.append(
                Notification(
                    user_id=user_id,
                    type="account_activated",
                    title="Ваш аккаунт активирован",
                    body="Ваш аккаунт был активирован администратором.",
                    url="/",
                    is_read=False,
                    created_at=datetime.now(timezone.utc),
                )
            )

    # Notify about profile data changes (name, email, social IDs, etc.)
    changed_data: list[str] = []
    for field, label in FIELD_LABELS.items():
        if field not in changes:
            continue
        old_val = {
            "full_name": old_full_name,
            "email": old_email,
            "telegram_id": old_telegram_id,
            "telegram_username": old_telegram_username,
        }.get(field)
        if changes[field] != old_val:
            changed_data.append(label)
    if changed_data:
        notifications.append(
            Notification(
                user_id=user_id,
                type="profile_updated",
                title="Данные аккаунта изменены администратором",
                body=f"Изменено: {', '.join(changed_data)}.",
                url="/profile",
                is_read=False,
                created_at=datetime.now(timezone.utc),
            )
        )

    if changes.get("password"):
        notifications.append(
            Notification(
                user_id=user_id,
                type="password_changed",
                title="Пароль изменён администратором",
                body="Администратор изменил ваш пароль. Если вы не запрашивали это — обратитесь в поддержку.",
                url="/profile",
                is_read=False,
                created_at=datetime.now(timezone.utc),
            )
        )

    for notif in notifications:
        session.add(notif)
    if notifications:
        await session.flush()
        # Mirror each in-app notification to Web Push so the browser/PWA hears
        # about account changes too (best-effort; respects the user's push
        # prefs and never breaks the request on failure).
        try:
            from shared.services.push_service import PushService

            push = PushService(session)
            for notif in notifications:
                await push.notify(
                    user,
                    event=notif.type,
                    title=notif.title,
                    body=notif.body or "",
                    url=notif.url or "/",
                )
        except Exception:  # noqa: BLE001
            pass

    return UserOut.model_validate(user)


@router.post("/{user_id}/reset-2fa", response_model=Message)
async def reset_user_2fa(
    user_id: int,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.USER_MANAGE)),
) -> Message:
    """Disable TOTP 2FA for a user (admin action)."""
    from datetime import datetime, timezone

    user = await UserService(session).get_or_404(user_id)
    user.totp_secret = None
    user.is_2fa_enabled = False
    await session.flush()

    # Notify the affected user
    from shared.models.notification import Notification

    session.add(
        Notification(
            user_id=user_id,
            type="2fa_reset",
            title="Двухфакторная аутентификация сброшена",
            body=f"Администратор {actor.email} отключил 2FA для вашего аккаунта.",
            url="/profile",
            is_read=False,
            created_at=datetime.now(timezone.utc),
        )
    )
    await session.flush()
    try:
        from shared.services.push_service import PushService

        await PushService(session).notify(
            user,
            event="2fa_reset",
            title="Двухфакторная аутентификация сброшена",
            body=f"Администратор {actor.email} отключил 2FA для вашего аккаунта.",
            url="/profile",
        )
    except Exception:  # noqa: BLE001
        pass
    await AuditService(session).log(
        "user.reset_2fa",
        user_id=actor.id,
        actor=actor.email,
        entity_type="user",
        entity_id=user_id,
        **meta,
    )
    return Message(detail="2FA отключена")


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


@router.post("/{user_id}/ban", response_model=UserOut)
async def ban_user(
    user_id: int,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.USER_MANAGE)),
) -> UserOut:
    """Ban a user account. Banned users cannot log in by any method."""
    from fastapi import HTTPException
    from shared.services.notify_router import notify_user

    if user_id == actor.id:
        raise HTTPException(status_code=400, detail="Нельзя заблокировать собственный аккаунт.")

    user = await UserService(session).get_or_404(user_id)
    user.is_banned = True
    await session.flush()

    await notify_user(
        session, user,
        type="account_deactivated",
        title="Ваш аккаунт заблокирован",
        body=f"Администратор {actor.email} заблокировал ваш аккаунт.",
        force_dm=True,
    )
    await AuditService(session).log(
        "user.ban",
        user_id=actor.id,
        actor=actor.email,
        entity_type="user",
        entity_id=user_id,
        **meta,
    )
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.post("/{user_id}/unban", response_model=UserOut)
async def unban_user(
    user_id: int,
    session: DBSession,
    meta: ClientMeta,
    actor: User = Depends(require_permission(Permission.USER_MANAGE)),
) -> UserOut:
    """Remove a ban from a user account."""
    from shared.services.notify_router import notify_user

    user = await UserService(session).get_or_404(user_id)
    user.is_banned = False
    await session.flush()

    await notify_user(
        session, user,
        type="account_activated",
        title="Ваш аккаунт разблокирован",
        body="Администратор разблокировал ваш аккаунт.",
        url="/",
    )
    await AuditService(session).log(
        "user.unban",
        user_id=actor.id,
        actor=actor.email,
        entity_type="user",
        entity_id=user_id,
        **meta,
    )
    await session.refresh(user)
    return UserOut.model_validate(user)
