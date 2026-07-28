"""add vk_id to users

Revision ID: 0009_vk_id
Revises: 0008_source_override
Create Date: 2026-07-27 15:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_vk_id"
down_revision: str | None = "0008_source_override"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("vk_id", sa.String(64), nullable=True))
    op.create_index("ix_users_vk_id", "users", ["vk_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_vk_id", table_name="users")
    op.drop_column("users", "vk_id")
