"""Add photo_url column to users

Revision ID: 0016_user_photo
Revises: 0015_notif
Create Date: 2026-07-30 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_user_photo"
down_revision: str | None = "0015_notif"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("photo_url", sa.String(1024), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "photo_url")
