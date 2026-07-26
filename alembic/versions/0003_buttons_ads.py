"""news buttons, channel username/avatar, ads table

Revision ID: 0003_buttons_ads
Revises: 0002_news_geolocation
Create Date: 2026-07-25 20:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_buttons_ads"
down_revision: str | None = "0002_news_geolocation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column(
        "news",
        sa.Column("buttons", postgresql.JSONB, nullable=False, server_default="[]"),
    )
    op.add_column("channels", sa.Column("username", sa.String(64), nullable=True))
    op.add_column("channels", sa.Column("avatar_url", sa.String(2048), nullable=True))

    op.create_table(
        "ads",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("advertiser", sa.String(255)),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="SET NULL")),
        sa.Column("buttons", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("media_urls", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("is_spoiler", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("scheduled_at", TS),
        sa.Column("published_at", TS),
        sa.Column("price", sa.Float),
        sa.Column("impressions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("clicks", sa.Integer, nullable=False, server_default="0"),
        sa.Column("published_message_ids", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("error", sa.Text),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ads_status", "ads", ["status"])


def downgrade() -> None:
    op.drop_table("ads")
    op.drop_column("channels", "avatar_url")
    op.drop_column("channels", "username")
    op.drop_column("news", "buttons")
