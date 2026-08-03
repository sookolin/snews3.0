"""Validation of Telegram Login ``id_token`` (OIDC) tokens.

The new Telegram Login library (``oauth.telegram.org/js/telegram-login.js``)
returns a signed OpenID Connect ``id_token`` (JWT). We verify its signature
against Telegram's JWKS and check the standard claims, per
https://core.telegram.org/bots/telegram-login#validating-id-tokens
"""

from __future__ import annotations

from functools import lru_cache

_ISSUER = "https://oauth.telegram.org"
_JWKS_URL = "https://oauth.telegram.org/.well-known/jwks.json"


@lru_cache(maxsize=1)
def _jwk_client():  # type: ignore[no-untyped-def]
    from jwt import PyJWKClient

    return PyJWKClient(_JWKS_URL)


def validate_id_token(id_token: str, client_id: int | str) -> dict | None:
    """Return the verified claims dict, or ``None`` when the token is invalid.

    Verifies the RS256/ES256 signature via Telegram's JWKS, and that ``iss`` is
    Telegram and ``aud`` matches our bot Client ID. The returned dict contains
    ``id`` (Telegram user id), ``name``, ``preferred_username``, ``picture`` …
    """
    if not id_token:
        return None
    try:
        import jwt

        signing_key = _jwk_client().get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256", "ES256", "EdDSA", "ES256K"],
            audience=str(client_id),
            issuer=_ISSUER,
            options={"require": ["exp", "iss", "aud"]},
        )
        return claims
    except Exception:  # noqa: BLE001 - any failure means "not authentic"
        return None
