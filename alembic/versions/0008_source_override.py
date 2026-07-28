"""news source override + ad heading

Revision ID: 0008_source_override
Revises: 0007_user_permissions
Create Date: 2026-07-27 14:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_source_override"
down_revision: str | None = "0007_user_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("news", sa.Column("source_name", sa.String(255), nullable=True))
    op.add_column(
        "news",
        sa.Column("hide_source", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.add_column("ads", sa.Column("heading", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("ads", "heading")
    op.drop_column("news", "hide_source")
    op.drop_column("news", "source_name")
