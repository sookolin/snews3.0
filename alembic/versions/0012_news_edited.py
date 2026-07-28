"""news is_edited flag + withdrawn status backfill

Revision ID: 0012_news_edited
Revises: 0011_publish_queue
Create Date: 2026-07-28 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_news_edited"
down_revision: str | None = "0011_publish_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "news",
        sa.Column("is_edited", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    # Retire statuses that are no longer part of the lifecycle.
    op.execute("UPDATE news SET status = 'processing' WHERE status = 'new'")
    op.execute("UPDATE news SET status = 'failed' WHERE status = 'duplicate'")


def downgrade() -> None:
    op.drop_column("news", "is_edited")
