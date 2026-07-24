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
