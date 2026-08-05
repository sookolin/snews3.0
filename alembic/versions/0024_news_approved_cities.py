"""Add approved_city_ids to news for partial multi-city approval

Revision ID: 0024_news_approved_cities
Revises: 0023_user_city_access
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from shared.db_types import JSONB

revision: str = "0024_news_approved_cities"
down_revision: str | None = "0023_user_city_access"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "news",
        sa.Column("approved_city_ids", JSONB, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("news", "approved_city_ids")
