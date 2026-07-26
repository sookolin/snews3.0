"""ai profile db credentials (api_key, base_url, embedding_model)

Revision ID: 0004_ai_credentials
Revises: 0003_buttons_ads
Create Date: 2026-07-26 16:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_ai_credentials"
down_revision: str | None = "0003_buttons_ads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_profiles", sa.Column("api_key", sa.String(512), nullable=True))
    op.add_column("ai_profiles", sa.Column("base_url", sa.String(512), nullable=True))
    op.add_column("ai_profiles", sa.Column("embedding_model", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_profiles", "embedding_model")
    op.drop_column("ai_profiles", "base_url")
    op.drop_column("ai_profiles", "api_key")
