"""Email notification service (SMTP), configured entirely from the web panel.

Answers the common question "which address does it send to?": the recipient is
whatever is set in Settings → Notifications → ``notifications.email_to``. All
SMTP parameters (host, port, user, password, from) are DB settings too, so no
code or .env changes are needed.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.mime.text import MIMEText

from sqlalchemy.ext.asyncio import AsyncSession

from shared.logging import get_logger
from shared.services.settings_service import SettingsService

log = get_logger("email")


class EmailService:
    """Send notification emails using DB-configured SMTP credentials."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _config(self) -> dict:
        s = SettingsService(self.session)
        return {
            "enabled": bool(await s.get("notifications.email_enabled", False)),
            "to": str(await s.get("notifications.email_to", "") or ""),
            "host": str(await s.get("notifications.smtp_host", "") or ""),
            "port": int(await s.get("notifications.smtp_port", 587) or 587),
            "user": str(await s.get("notifications.smtp_user", "") or ""),
            "password": str(await s.get("notifications.smtp_password", "") or ""),
            "from": str(await s.get("notifications.smtp_from", "") or ""),
        }

    async def send(self, subject: str, body: str, to: str | None = None) -> bool:
        """Send an email; returns True on success. No-op when disabled/misconfigured."""
        cfg = await self._config()
        recipient = to or cfg["to"]
        if not cfg["enabled"] or not cfg["host"] or not recipient:
            return False

        def _send() -> None:
            message = MIMEText(body, "html", "utf-8")
            message["Subject"] = subject
            message["From"] = cfg["from"] or cfg["user"] or "noreply@localhost"
            message["To"] = recipient
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as server:
                server.ehlo()
                try:
                    server.starttls()
                    server.ehlo()
                except smtplib.SMTPException:
                    pass  # server without STARTTLS
                if cfg["user"]:
                    server.login(cfg["user"], cfg["password"])
                server.send_message(message)

        try:
            await asyncio.to_thread(_send)
            log.info("email_sent", to=recipient, subject=subject)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("email_send_failed", error=str(exc))
            return False
