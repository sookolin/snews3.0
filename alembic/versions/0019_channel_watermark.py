"""Per-channel watermark profile binding.

Adds ``channels.watermark_id`` so each channel can pick which watermark profile
is applied to its media (NULL = fall back to the default active profile).

Revision ID: 0019_channel_watermark
Revises: 0018_multichannel_weather
Create Date: 2026-08-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0019_channel_watermark"
down_revision: str | None = "0018_multichannel_weather"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("watermark_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_channels_watermark_id_watermark_profiles",
        "channels",
        "watermark_profiles",
        ["watermark_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_channels_watermark_id_watermark_profiles",
        "channels",
        type_="foreignkey",
    )
    op.drop_column("channels", "watermark_id")
