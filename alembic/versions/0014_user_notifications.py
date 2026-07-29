"""user notification prefs + web push subscriptions

Revision ID: 0014_user_notify
Revises: 0013_city_kind
Create Date: 2026-07-29 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from shared.db_types import JSONB

revision: str = "0014_user_notify"
down_revision: str | None = "0013_city_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("notify_prefs", JSONB, nullable=False, server_default="{}"),
    )
    op.add_column(
        "users",
        sa.Column("push_subscriptions", JSONB, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("users", "push_subscriptions")
    op.drop_column("users", "notify_prefs")
