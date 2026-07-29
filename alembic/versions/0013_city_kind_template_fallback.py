"""city kind/world bucket + template custom emoji fallback

Revision ID: 0013_city_kind
Revises: 0012_news_edited
Create Date: 2026-07-29 10:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_city_kind"
down_revision: str | None = "0012_news_edited"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cities",
        sa.Column("kind", sa.String(16), nullable=False, server_default="city"),
    )
    op.add_column(
        "cities",
        sa.Column(
            "is_world_bucket", sa.Boolean, nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "templates",
        sa.Column("custom_emoji_fallback", sa.String(16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("templates", "custom_emoji_fallback")
    op.drop_column("cities", "is_world_bucket")
    op.drop_column("cities", "kind")
