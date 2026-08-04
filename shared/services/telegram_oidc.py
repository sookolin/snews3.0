"""Validation of Telegram Login ``id_token`` (OIDC) tokens.

The new Telegram Login library (``oauth.telegram.org/js/telegram-login.js``)
returns a signed OpenID Connect ``id_token`` (JWT). We verify its signature
against Telegram's JWKS and check the standard claims, per
https://core.telegram.org/bots/telegram-login#validating-id-tokens
"""

from __future__ import annotations

from functools import lru_cache

from shared.logging import get_logger

log = get_logger("telegram_oidc")

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
        # Verify signature + iss + exp, but check ``aud`` ourselves: Telegram may
        # encode it as a number or a string, and PyJWT's aud check is strict on
        # type, which caused false "invalid token" rejections.
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256", "ES256", "EdDSA", "ES256K"],
            issuer=_ISSUER,
            leeway=30,
            options={"require": ["exp", "iss"], "verify_aud": False},
        )
        aud = claims.get("aud")
        aud_values = aud if isinstance(aud, list) else [aud]
        if str(client_id) not in {str(a) for a in aud_values}:
            log.warning("telegram_oidc_aud_mismatch", aud=aud, expected=str(client_id))
            return None
        return claims
    except Exception as exc:  # noqa: BLE001 - any failure means "not authentic"
        # Log the concrete reason so misconfig (wrong aud/alg/expired) is visible.
        log.warning("telegram_oidc_invalid", error=str(exc), error_type=type(exc).__name__)
        return None
