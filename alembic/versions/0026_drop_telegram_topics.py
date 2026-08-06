"""Drop Telegram forum-topic columns (feature removed)

Removes ``cities.telegram_topic_id`` and ``channels.topic_id``. Forum-topic
support (message_thread_id routing) has been removed in favor of a single
moderation group / plain channel chats.

Revision ID: 0026_drop_telegram_topics
Revises: 0025_user_role_value_fix
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_drop_telegram_topics"
down_revision: str | None = "0025_user_role_value_fix"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("cities", "telegram_topic_id")
    op.drop_column("channels", "topic_id")


def downgrade() -> None:
    op.add_column("cities", sa.Column("telegram_topic_id", sa.Integer, nullable=True))
    op.add_column("channels", sa.Column("topic_id", sa.Integer, nullable=True))
