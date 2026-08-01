"""news target cities (multi-channel) + per-city daily weather

Revision ID: 0018_multichannel_weather
Revises: 0017_user_ban
Create Date: 2026-08-01 20:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_multichannel_weather"
down_revision: str | None = "0017_user_ban"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Many-to-many: one news item -> several target cities (channels).
    op.create_table(
        "news_target_cities",
        sa.Column(
            "news_id",
            sa.Integer,
            sa.ForeignKey("news.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "city_id",
            sa.Integer,
            sa.ForeignKey("cities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    # Backfill: every existing news becomes its own single target so behaviour
    # is unchanged for old rows.
    op.execute(
        "INSERT INTO news_target_cities (news_id, city_id) "
        "SELECT id, city_id FROM news WHERE city_id IS NOT NULL"
    )

    # Per-city daily weather post configuration.
    op.add_column(
        "cities",
        sa.Column("weather_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.add_column("cities", sa.Column("weather_time", sa.String(5), nullable=True))
    op.add_column("cities", sa.Column("weather_lat", sa.Float, nullable=True))
    op.add_column("cities", sa.Column("weather_lon", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("cities", "weather_lon")
    op.drop_column("cities", "weather_lat")
    op.drop_column("cities", "weather_time")
    op.drop_column("cities", "weather_enabled")
    op.drop_table("news_target_cities")
