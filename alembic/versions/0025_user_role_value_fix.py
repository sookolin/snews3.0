"""Normalize users.role to lowercase enum values

The ``role`` column used to be a SQLAlchemy ``Enum(UserRole, native_enum=False)``.
That column type persists Python ``Enum.name`` (e.g. ``SUPER_ADMIN``) rather
than ``Enum.value`` (``super_admin``) and transparently converted between the
two on every read/write. The column was changed to a plain ``String(32)`` to
allow custom roles, which removed that automatic conversion — so any row
still holding the old uppercase enum *name* is now an unrecognized role
everywhere permissions are checked (``Permission`` values compare against
``UserRole.value``, e.g. ``"super_admin"``). This normalizes existing rows.

Revision ID: 0025_user_role_value_fix
Revises: 0024_news_approved_cities
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_user_role_value_fix"
down_revision: str | None = "0024_news_approved_cities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Map of legacy uppercase Enum.name -> lowercase Enum.value for every
# built-in role (see shared.enums.UserRole).
_NAME_TO_VALUE = {
    "SUPER_ADMIN": "super_admin",
    "ADMIN": "admin",
    "MODERATOR": "moderator",
    "EDITOR": "editor",
    "REVIEWER": "reviewer",
}


def upgrade() -> None:
    conn = op.get_bind()
    for name, value in _NAME_TO_VALUE.items():
        conn.execute(
            sa.text("UPDATE users SET role = :value WHERE role = :name"),
            {"value": value, "name": name},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for name, value in _NAME_TO_VALUE.items():
        conn.execute(
            sa.text("UPDATE users SET role = :name WHERE role = :value"),
            {"value": value, "name": name},
        )
