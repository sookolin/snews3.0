"""news timings, reply threading, world-news flag

Revision ID: 0010_news_meta
Revises: 0009_vk_id
Create Date: 2026-07-27 17:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_news_meta"
down_revision: str | None = "0009_vk_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("news", sa.Column("source_published_at", TS, nullable=True))
    op.add_column("news", sa.Column("processed_at", TS, nullable=True))
    op.add_column(
        "news",
        sa.Column("reply_to_news_id", sa.Integer, sa.ForeignKey("news.id", ondelete="SET NULL")),
    )
    op.add_column(
        "news",
        sa.Column("is_world_news", sa.Boolean, nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("news", "is_world_news")
    op.drop_column("news", "reply_to_news_id")
    op.drop_column("news", "processed_at")
    op.drop_column("news", "source_published_at")
