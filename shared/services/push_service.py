"""Web Push delivery for the admin panel (PWA / iOS home-screen).

VAPID keys live in the settings table so no extra env wiring is needed: the
first call generates a pair, and the public key is handed to the browser when it
subscribes. Sending is best-effort — a device that answers 404/410 is gone, so
its subscription is dropped from the user record.
"""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.user import User
from shared.services.settings_service import SettingsService

logger = structlog.get_logger(__name__)

PUBLIC_KEY = "push.vapid_public_key"
PRIVATE_KEY = "push.vapid_private_key"
CONTACT = "push.vapid_contact"


def _b64(raw: bytes) -> str:
    """URL-safe base64 without padding, as the Web Push spec expects."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _generate_keys() -> tuple[str, str]:
    """Create a VAPID key pair (public in raw form, private as DER base64)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private = ec.generate_private_key(ec.SECP256R1())
    public_raw = private.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    private_der = private.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return _b64(public_raw), _b64(private_der)


class PushService:
    """Server side of Web Push: key management plus fan-out to devices."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = SettingsService(session)

    async def public_key(self) -> str:
        """Public VAPID key for `pushManager.subscribe`, generated on demand."""
        key = await self.settings.get(PUBLIC_KEY, "")
        if key:
            return str(key)
        public, private = await asyncio.to_thread(_generate_keys)
        await self.settings.set(PUBLIC_KEY, public, category="push")
        await self.settings.set(PRIVATE_KEY, private, category="push", is_secret=True)
        # Ensure a valid VAPID contact — several push services reject
        # "mailto:admin@localhost". Derive it from the configured admin URL.
        if not await self.settings.get(CONTACT, ""):
            from shared.config import settings as app_settings

            host = ""
            try:
                from urllib.parse import urlparse

                host = urlparse(str(getattr(app_settings, "admin_panel_url", "") or "")).hostname or ""
            except Exception:
                host = ""
            contact = f"mailto:admin@{host}" if host else "mailto:admin@sonews.ru"
            await self.settings.set(CONTACT, contact, category="push")
        await self.session.commit()
        logger.info("vapid_keys_generated")
        return public

    async def _private_pem(self) -> str | None:
        """Private key as PEM, the format pywebpush accepts."""
        raw = str(await self.settings.get(PRIVATE_KEY, "") or "")
        if not raw:
            return None
        from cryptography.hazmat.primitives import serialization

        der = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        private = serialization.load_der_private_key(der, password=None)
        return private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()

    def _send_one(self, device: dict, payload: str, pem: str, contact: str) -> int:
        """Blocking single-device send; returns the HTTP status (0 on error)."""
        from pywebpush import WebPushException, webpush

        try:
            response = webpush(
                subscription_info={"endpoint": device["endpoint"], "keys": device.get("keys", {})},
                data=payload,
                vapid_private_key=pem,
                vapid_claims={"sub": contact},
                timeout=10,
            )
            return int(getattr(response, "status_code", 200))
        except WebPushException as exc:
            status = int(getattr(getattr(exc, "response", None), "status_code", 0) or 0)
            if status not in (404, 410):
                logger.warning("push_send_failed", error=str(exc), status=status)
            return status
        except Exception as exc:  # network/DNS issues shouldn't break the caller
            logger.warning("push_send_error", error=str(exc))
            return 0

    async def notify(self, user: User, event: str, title: str, body: str, url: str = "/") -> int:
        """Push one event to every device of a user who opted into that event."""
        prefs = (user.notify_prefs or {}).get("push") or {}
        if not prefs.get(event):
            return 0
        devices = list(user.push_subscriptions or [])
        if not devices:
            return 0
        pem = await self._private_pem()
        if pem is None:
            return 0
        contact = str(await self.settings.get(CONTACT, "") or "mailto:admin@localhost")
        payload = json.dumps({"title": title, "body": body, "url": url, "event": event})

        alive: list[dict] = []
        sent = 0
        for device in devices:
            status = await asyncio.to_thread(self._send_one, device, payload, pem, contact)
            if status in (404, 410):
                continue  # subscription expired — drop it
            alive.append(device)
            if 200 <= status < 300:
                sent += 1
        if len(alive) != len(devices):
            user.push_subscriptions = alive
            await self.session.commit()
        return sent

    async def broadcast(
        self, event: str, title: str, body: str, url: str = "/", **filters: Any
    ) -> int:
        """Push an event to every active user subscribed to it."""
        stmt = select(User).where(User.is_active.is_(True))
        users = (await self.session.scalars(stmt)).all()
        total = 0
        for user in users:
            if filters.get("user_ids") and user.id not in filters["user_ids"]:
                continue
            total += await self.notify(user, event, title, body, url)
        return total
