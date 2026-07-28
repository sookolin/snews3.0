"""ad geolocation + recurring schedule

Revision ID: 0006_ad_schedule
Revises: 0005_more_settings
Create Date: 2026-07-27 10:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_ad_schedule"
down_revision: str | None = "0005_more_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ads", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("ads", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("ads", sa.Column("location_title", sa.String(255), nullable=True))
    op.add_column("ads", sa.Column("location_address", sa.String(512), nullable=True))
    op.add_column(
        "ads", sa.Column("schedule", postgresql.JSONB, nullable=False, server_default="{}")
    )
    op.add_column(
        "ads",
        sa.Column("auto_publish", sa.Boolean, nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("ads", "auto_publish")
    op.drop_column("ads", "schedule")
    op.drop_column("ads", "location_address")
    op.drop_column("ads", "location_title")
    op.drop_column("ads", "longitude")
    op.drop_column("ads", "latitude")
