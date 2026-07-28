"""user oauth links + per-user permission overrides

Revision ID: 0007_user_permissions
Revises: 0006_ad_schedule
Create Date: 2026-07-27 11:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_user_permissions"
down_revision: str | None = "0006_ad_schedule"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("yandex_id", sa.String(64), nullable=True))
    op.create_index("ix_users_yandex_id", "users", ["yandex_id"], unique=True)
    op.add_column(
        "users",
        sa.Column("permissions", postgresql.JSONB, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("users", "permissions")
    op.drop_index("ix_users_yandex_id", table_name="users")
    op.drop_column("users", "yandex_id")
