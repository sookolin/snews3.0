"""Add telegram_username column to users

New users are provisioned by binding a Telegram account (id + username), so we
store the username alongside the numeric id.

Revision ID: 0021_user_tg_username
Revises: 0020_city_weather_last_published
Create Date: 2026-08-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_user_tg_username"
down_revision: str | None = "0020_city_weather_last_published"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("telegram_username", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "telegram_username")
