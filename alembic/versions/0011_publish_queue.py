"""source url override, ai_processed_at, publish_immediately

Revision ID: 0011_publish_queue
Revises: 0010_news_meta
Create Date: 2026-07-27 21:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_publish_queue"
down_revision: str | None = "0010_news_meta"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("news", sa.Column("source_url_override", sa.String(2048), nullable=True))
    op.add_column("news", sa.Column("ai_processed_at", TS, nullable=True))
    op.add_column(
        "news",
        sa.Column("publish_immediately", sa.Boolean, nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("news", "publish_immediately")
    op.drop_column("news", "ai_processed_at")
    op.drop_column("news", "source_url_override")
