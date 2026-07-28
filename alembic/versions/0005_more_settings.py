"""template uppercase, news emoji, ai auto_emoji, ad template/erid/media_files

Revision ID: 0005_more_settings
Revises: 0004_ai_credentials
Create Date: 2026-07-27 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_more_settings"
down_revision: str | None = "0004_ai_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "templates",
        sa.Column("uppercase_title", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.add_column("news", sa.Column("emoji", sa.String(16), nullable=True))
    op.add_column(
        "ai_profiles",
        sa.Column("auto_emoji", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "ads", sa.Column("template_id", sa.Integer, sa.ForeignKey("templates.id", ondelete="SET NULL"))
    )
    op.add_column(
        "ads", sa.Column("media_files", postgresql.JSONB, nullable=False, server_default="[]")
    )
    op.add_column("ads", sa.Column("erid", sa.String(128), nullable=True))
    op.add_column("ads", sa.Column("advertiser_inn", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("ads", "advertiser_inn")
    op.drop_column("ads", "erid")
    op.drop_column("ads", "media_files")
    op.drop_column("ads", "template_id")
    op.drop_column("ai_profiles", "auto_emoji")
    op.drop_column("news", "emoji")
    op.drop_column("templates", "uppercase_title")
