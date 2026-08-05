"""Add city_access to users for city-scoped RBAC

Empty list means unrestricted (sees every city); non-empty restricts the
user to moderating/viewing only the listed cities.

Revision ID: 0023_user_city_access
Revises: 0022_source_show_autopublish
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from shared.db_types import JSONB

revision: str = "0023_user_city_access"
down_revision: str | None = "0022_source_show_autopublish"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("city_access", JSONB, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("users", "city_access")
