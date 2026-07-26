"""add geolocation fields to news

Revision ID: 0002_news_geolocation
Revises: 0001_initial
Create Date: 2026-07-24 16:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_news_geolocation"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("news", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("news", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("news", sa.Column("location_title", sa.String(255), nullable=True))
    op.add_column("news", sa.Column("location_address", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("news", "location_address")
    op.drop_column("news", "location_title")
    op.drop_column("news", "longitude")
    op.drop_column("news", "latitude")
