"""Cross-dialect column types.

Uses PostgreSQL native ``JSONB`` / ``ARRAY`` when available, and falls back to
portable JSON-based implementations on other dialects (e.g. SQLite for tests).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import ARRAY as PGARRAY
from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
from sqlalchemy.types import TypeDecorator


class JSONB(TypeDecorator):
    """JSONB on PostgreSQL, generic JSON elsewhere."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGJSONB())
        return dialect.type_descriptor(JSON())


class StringArray(TypeDecorator):
    """``ARRAY(String)`` on PostgreSQL, JSON list of strings elsewhere."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGARRAY(String))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return [] if dialect.name != "postgresql" else value
        return list(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        return list(value) if value is not None else []


class FloatArray(TypeDecorator):
    """``ARRAY(Float)`` on PostgreSQL, JSON list of floats elsewhere."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            from sqlalchemy import Float

            return dialect.type_descriptor(PGARRAY(Float))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return list(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        return list(value) if value is not None else None
