"""Track the last date a city's weather post was published.

Adds ``cities.weather_last_published_on`` (YYYY-MM-DD, UI-local date) so the
weather scheduler can publish within a tolerance window without posting twice
on the same day.

Revision ID: 0020_city_weather_last_published
Revises: 0019_channel_watermark
Create Date: 2026-08-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0020_city_weather_last_published"
down_revision: str | None = "0019_channel_watermark"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cities",
        sa.Column("weather_last_published_on", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cities", "weather_last_published_on")
