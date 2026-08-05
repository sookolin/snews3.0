"""Add show_in_post and auto_publish to sources

- ``show_in_post``: when off, news from this source publish with no source
  line, regardless of the per-post override.
- ``auto_publish``: when on, news from this source are approved and
  published automatically without manual moderation.

Revision ID: 0022_source_show_autopublish
Revises: 0021_user_tg_username
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_source_show_autopublish"
down_revision: str | None = "0021_user_tg_username"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("show_in_post", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "sources",
        sa.Column("auto_publish", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("sources", "auto_publish")
    op.drop_column("sources", "show_in_post")
