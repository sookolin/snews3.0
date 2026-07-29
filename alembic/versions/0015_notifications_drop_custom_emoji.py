"""notifications table + drop template custom_emoji columns

Revision ID: 0015_notif
Revises: 0014_user_notify
Create Date: 2026-07-29 15:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_notif"
down_revision: str | None = "0014_user_notify"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Notifications ────────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("type", sa.String(64), nullable=False, server_default="system"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("url", sa.String(1024), nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── Drop custom_emoji columns from templates ─────────────────────────────
    op.drop_column("templates", "custom_emoji_id")
    op.drop_column("templates", "custom_emoji_fallback")


def downgrade() -> None:
    op.add_column("templates", sa.Column("custom_emoji_fallback", sa.String(16), nullable=True))
    op.add_column("templates", sa.Column("custom_emoji_id", sa.String(64), nullable=True))
    op.drop_table("notifications")
