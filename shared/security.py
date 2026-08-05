"""Security utilities: password hashing, JWT tokens, TOTP 2FA, permissions."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt
import pyotp

from shared.config import settings
from shared.enums import Permission, UserRole, permissions_for_role
from shared.exceptions import AuthenticationError

TokenType = Literal["access", "refresh"]

# bcrypt operates on at most 72 bytes; longer inputs must be truncated.
_BCRYPT_MAX_BYTES = 72


def _to_bcrypt_bytes(password: str) -> bytes:
    """Encode and safely truncate a password to bcrypt's 72-byte limit."""
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(_to_bcrypt_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(_to_bcrypt_bytes(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _create_token(
    subject: str | int,
    token_type: TokenType,
    expires_delta: timedelta,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": secrets.token_hex(8),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> str:
    """Create a short-lived access token."""
    return _create_token(
        subject,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
        extra,
    )


def create_refresh_token(subject: str | int) -> str:
    """Create a long-lived refresh token."""
    return _create_token(
        subject,
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    """Decode & validate a JWT. Raises ``AuthenticationError`` on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token has expired", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid token", code="token_invalid") from exc

    if expected_type is not None and payload.get("type") != expected_type:
        raise AuthenticationError("Invalid token type", code="token_type_invalid")
    return payload


# ── 2FA (TOTP) ────────────────────────────────────────────────────────────────
def generate_totp_secret() -> str:
    """Generate a base32 TOTP secret."""
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, email: str) -> str:
    """Return an otpauth:// URI for QR provisioning."""
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=settings.app_name)


def verify_totp(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code (±1 window)."""
    return pyotp.TOTP(secret).verify(code, valid_window=1)


# ── Permissions ────────────────────────────────────────────────────────────────
def has_permission(role: UserRole, permission: Permission) -> bool:
    """Check whether a role grants the given permission."""
    if role == UserRole.SUPER_ADMIN:
        return True
    return permission in permissions_for_role(role)


def user_has_permission(user: object, permission: Permission) -> bool:
    """Check a permission for a user, applying per-user grant/deny overrides.

    ``user.permissions`` may contain ``{"grant": [...], "deny": [...]}`` with
    permission values; ``deny`` wins over everything except SUPER_ADMIN.

    For a city-scoped permission (see ``CITY_SCOPED_PERMISSIONS``) that the
    role only grants for specific cities ("Разрешить (выбранные)"), this
    still returns ``True`` — it answers "can the user do this at all, for at
    least one city". Which cities exactly are gated separately by
    :func:`resolve_city_scope`.
    """
    role = getattr(user, "role", None)
    overrides = getattr(user, "permissions", None) or {}
    deny = set(overrides.get("deny") or [])
    grant = set(overrides.get("grant") or [])

    if permission.value in deny:
        return False
    if permission.value in grant:
        return True
    if role is None:
        return False
    if has_permission(role, permission):
        return True
    # Role-level city-scoped grant (e.g. "Разрешить (выбранные)" with a city
    # list) still grants the permission itself even though the role's plain
    # default set does not include it.
    scope = resolve_city_scope(user, permission)
    return scope.has_access


# ── City-scoped permissions (roles + per-user overrides) ───────────────────
class CityScope:
    """Resolved city-based access for one permission.

    - ``has_access=False``: the user cannot use this permission for ANY city.
    - ``unrestricted=True``: every city is allowed (subject to ``deny``).
    - ``allow``: when not ``None``, only these city ids are allowed.
    - ``deny``: city ids explicitly excluded on top of ``allow``/unrestricted.

    ``city_id=None`` (world/unassigned items) is always permitted when
    ``has_access`` is true — city scoping only restricts real cities.
    """

    __slots__ = ("has_access", "unrestricted", "allow", "deny")

    def __init__(
        self,
        has_access: bool,
        *,
        unrestricted: bool = False,
        allow: frozenset[int] | None = None,
        deny: frozenset[int] = frozenset(),
    ) -> None:
        self.has_access = has_access
        self.unrestricted = unrestricted
        self.allow = allow
        self.deny = deny

    def permits(self, city_id: int | None) -> bool:
        if not self.has_access:
            return False
        if city_id is None:
            return True
        if city_id in self.deny:
            return False
        if self.unrestricted:
            return True
        return self.allow is not None and city_id in self.allow

    def allowed_city_ids(self) -> list[int] | None:
        """Explicit allow-list, or ``None`` when unrestricted (no allow-list)."""
        if not self.has_access:
            return []
        if self.unrestricted:
            return None
        return sorted(self.allow or ())


def _role_permission_city_scope(
    role: object, permission: Permission, role_cfg: dict
) -> CityScope:
    """Resolve a role's city scope for ``permission`` from its stored config.

    ``role_cfg`` is one role's entry from the ``roles.permissions`` setting:
    ``{"grant": [...], "deny": [...], "city_scoped": {perm: {"mode": ..., "cities": [...]}}}``.
    """
    scoped = (role_cfg.get("city_scoped") or {}).get(permission.value)
    default_has = has_permission(role, permission) if role is not None else False

    if not scoped:
        deny_flat = set(role_cfg.get("deny") or [])
        grant_flat = set(role_cfg.get("grant") or [])
        if permission.value in deny_flat:
            return CityScope(False)
        if permission.value in grant_flat:
            return CityScope(True, unrestricted=True)
        return CityScope(default_has, unrestricted=default_has)

    mode = scoped.get("mode", "role")
    cities = frozenset(int(c) for c in (scoped.get("cities") or []))

    if mode == "grant":
        return CityScope(True, unrestricted=True)
    if mode == "deny":
        return CityScope(False)
    if mode == "grant_selected":
        return CityScope(bool(cities), allow=cities)
    if mode == "deny_selected":
        return CityScope(default_has, unrestricted=default_has, deny=cities)
    # "role" (explicit default) or unrecognized → fall back to the role's
    # built-in default permission set, unrestricted.
    return CityScope(default_has, unrestricted=default_has)


def resolve_city_scope(user: object, permission: Permission) -> CityScope:
    """Resolve the effective per-city access ``user`` has for ``permission``.

    Precedence (highest wins):
      1. Personal per-user permission override (``user.permissions``) — global,
         not city-scoped, exactly like :func:`user_has_permission`.
      2. Personal city restriction (``user.city_access``) — when non-empty it
         REPLACES the role's own city scoping entirely (per requirement: a
         city grant set directly on the user overrides role-level grants).
      3. Role-level city-scoped config (``roles.permissions[role].city_scoped``).
      4. The role's built-in default permission set, unrestricted.

    Super admins are always fully unrestricted.
    """
    role = getattr(user, "role", None)
    if role == UserRole.SUPER_ADMIN:
        return CityScope(True, unrestricted=True)

    overrides = getattr(user, "permissions", None) or {}
    deny = set(overrides.get("deny") or [])
    grant = set(overrides.get("grant") or [])
    if permission.value in deny:
        return CityScope(False)

    personal_grant = permission.value in grant

    user_cities = getattr(user, "city_access", None) or []
    role_cfg = getattr(user, "_role_perm_cfg", None) or {}
    role_scope = _role_permission_city_scope(role, permission, role_cfg)

    has_access = personal_grant or role_scope.has_access
    if not has_access:
        return CityScope(False)

    if user_cities:
        # A city restriction set directly on the user's card always wins,
        # replacing whatever the role would otherwise allow/deny.
        return CityScope(True, allow=frozenset(int(c) for c in user_cities))

    if personal_grant:
        return CityScope(True, unrestricted=True)

    return role_scope


# ── City access (RBAC scoping) ──────────────────────────────────────────────
def user_city_access(
    user: object, permission: Permission = Permission.NEWS_VIEW
) -> list[int] | None:
    """Return the list of city ids ``user`` is restricted to for ``permission``.

    ``None`` means unrestricted access to every city. Resolution order:

    1. A personal ``city_access`` list on the user's card always wins and
       replaces whatever the role grants (see :func:`resolve_city_scope`).
    2. Otherwise the role's own city-scoped grant for this permission
       ("Разрешить (выбранные)" / "Запретить (выбранные)" in Права ролей).
    3. Otherwise unrestricted, as long as the role/user has the permission at
       all (checked by the caller via ``require_permission``).

    An "edit"-style permission (moderate/publish/delete/manage) is further
    intersected with the matching "view" permission's scope — you cannot act
    on a city you are not allowed to see (see ``CITY_SCOPE_REQUIRES_VIEW``).
    """
    from shared.enums import CITY_SCOPE_REQUIRES_VIEW

    role = getattr(user, "role", None)
    if role == UserRole.SUPER_ADMIN:
        return None

    scope = resolve_city_scope(user, permission)
    ids = scope.allowed_city_ids()

    view_perm = CITY_SCOPE_REQUIRES_VIEW.get(permission)
    if view_perm is not None:
        view_scope = resolve_city_scope(user, view_perm)
        view_ids = view_scope.allowed_city_ids()
        if ids is None:
            ids = view_ids
        elif view_ids is not None:
            ids = [cid for cid in ids if cid in set(view_ids)]
    return ids


def user_can_access_city(
    user: object, city_id: int | None, permission: Permission = Permission.NEWS_VIEW
) -> bool:
    """True if ``user`` may use ``permission`` for ``city_id``.

    ``city_id`` of ``None`` (e.g. world/unassigned news) is always visible —
    city restriction only scopes real cities.
    """
    allowed = user_city_access(user, permission)
    if allowed is None or city_id is None:
        return True
    return city_id in allowed
