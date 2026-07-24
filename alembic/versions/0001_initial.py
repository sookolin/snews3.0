"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("is_2fa_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("totp_secret", sa.String(64)),
        sa.Column("telegram_id", sa.BigInteger),
        sa.Column("language", sa.String(8), nullable=False, server_default="ru"),
        sa.Column("last_login_at", TS),
        *_timestamps(),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    # templates
    op.create_table(
        "templates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("format", sa.String(32), nullable=False, server_default="telegram_html"),
        sa.Column("header", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("footer", sa.Text, nullable=False),
        sa.Column("separator", sa.String(64), nullable=False, server_default="\n\n"),
        sa.Column("custom_emoji_id", sa.String(64)),
        sa.Column("subscribe_link", sa.String(2048)),
        sa.Column("variables", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("disable_web_preview", sa.Boolean, nullable=False, server_default=sa.true()),
        *_timestamps(),
    )

    # ai_profiles
    op.create_table(
        "ai_profiles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("provider", sa.String(32), nullable=False, server_default="anthropic"),
        sa.Column("model", sa.String(128)),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("instructions", sa.Text),
        sa.Column("tone", sa.String(128)),
        sa.Column("style", sa.String(128)),
        sa.Column("temperature", sa.Float, nullable=False, server_default="0.4"),
        sa.Column("max_tokens", sa.Integer, nullable=False, server_default="2048"),
        sa.Column("generate_embeddings", sa.Boolean, nullable=False, server_default=sa.true()),
        *_timestamps(),
    )

    # watermark_profiles
    op.create_table(
        "watermark_profiles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("logo_path", sa.String(1024)),
        sa.Column("text", sa.String(255)),
        sa.Column("position", sa.String(16), nullable=False, server_default="bottom-right"),
        sa.Column("margin_x", sa.Integer, nullable=False, server_default="20"),
        sa.Column("margin_y", sa.Integer, nullable=False, server_default="20"),
        sa.Column("scale", sa.Float, nullable=False, server_default="0.18"),
        sa.Column("opacity", sa.Float, nullable=False, server_default="0.75"),
        sa.Column("font_size", sa.Integer, nullable=False, server_default="32"),
        sa.Column("color", sa.String(16), nullable=False, server_default="#FFFFFF"),
        sa.Column("shadow", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("shadow_color", sa.String(16), nullable=False, server_default="#000000"),
        *_timestamps(),
    )

    # cities
    op.create_table(
        "cities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("keywords", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("extra_keywords", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("exclude_keywords", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("region", sa.String(255)),
        sa.Column("country", sa.String(255)),
        sa.Column("language", sa.String(8), nullable=False, server_default="ru"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("telegram_topic_id", sa.Integer),
        sa.Column("template_id", sa.Integer),
        *_timestamps(),
    )
    op.create_index("ix_cities_name", "cities", ["name"])
    op.create_index("ix_cities_slug", "cities", ["slug"], unique=True)

    # sources
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("parser_engine", sa.String(32), nullable=False, server_default="auto"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
        sa.Column("check_interval_seconds", sa.Integer, nullable=False, server_default="300"),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="30"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("use_proxy", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("proxy_url", sa.String(2048)),
        sa.Column("headers", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("cookies", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("auth", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("selectors", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("last_checked_at", TS),
        sa.Column("last_success_at", TS),
        sa.Column("last_error", sa.Text),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        *_timestamps(),
    )

    # source_cities (m2m)
    op.create_table(
        "source_cities",
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("city_id", sa.Integer, sa.ForeignKey("cities.id", ondelete="CASCADE"), primary_key=True),
    )

    # channels
    op.create_table(
        "channels",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("city_id", sa.Integer, sa.ForeignKey("cities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("chat_id", sa.String(64), nullable=False),
        sa.Column("topic_id", sa.Integer),
        sa.Column("publish_mode", sa.String(16), nullable=False, server_default="immediate"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("schedule_from_minute", sa.Integer),
        sa.Column("schedule_to_minute", sa.Integer),
        sa.Column("min_interval_seconds", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("template_id", sa.Integer, sa.ForeignKey("templates.id", ondelete="SET NULL")),
        *_timestamps(),
    )
    op.create_index("ix_channels_city_id", "channels", ["city_id"])

    # news
    op.create_table(
        "news",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("original_title", sa.String(1024)),
        sa.Column("original_text", sa.Text, nullable=False),
        sa.Column("original_url", sa.String(2048)),
        sa.Column("title", sa.String(1024)),
        sa.Column("text", sa.Text),
        sa.Column("status", sa.String(32), nullable=False, server_default="new"),
        sa.Column("origin", sa.String(16), nullable=False, server_default="parser"),
        sa.Column("city_id", sa.Integer, sa.ForeignKey("cities.id", ondelete="SET NULL")),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id", ondelete="SET NULL")),
        sa.Column("template_id", sa.Integer, sa.ForeignKey("templates.id", ondelete="SET NULL")),
        sa.Column("ai_profile_id", sa.Integer, sa.ForeignKey("ai_profiles.id", ondelete="SET NULL")),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("simhash", sa.BigInteger),
        sa.Column("embedding", postgresql.ARRAY(sa.Float)),
        sa.Column("match_score", sa.Float),
        sa.Column("matched_keywords", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("is_spoiler", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("apply_watermark", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("scheduled_at", TS),
        sa.Column("published_at", TS),
        sa.Column("submitted_by_telegram_id", sa.BigInteger),
        sa.Column("submitted_anonymously", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("author_name", sa.String(255)),
        sa.Column("moderated_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("rejection_reason", sa.Text),
        sa.Column("moderation_message_id", sa.BigInteger),
        sa.Column("published_message_ids", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("error", sa.Text),
        *_timestamps(),
    )
    op.create_index("ix_news_status", "news", ["status"])
    op.create_index("ix_news_content_hash", "news", ["content_hash"])

    # media_assets
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("news_id", sa.Integer, sa.ForeignKey("news.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("file_path", sa.String(1024)),
        sa.Column("processed_path", sa.String(1024)),
        sa.Column("remote_url", sa.String(2048)),
        sa.Column("telegram_file_id", sa.String(512)),
        sa.Column("mime_type", sa.String(128)),
        sa.Column("file_size", sa.Integer),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("duration", sa.Integer),
        sa.Column("caption", sa.Text),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_spoiler", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("thumbnail_path", sa.String(1024)),
        *_timestamps(),
    )
    op.create_index("ix_media_assets_news_id", "media_assets", ["news_id"])

    # news_versions
    op.create_table(
        "news_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("news_id", sa.Integer, sa.ForeignKey("news.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("title", sa.String(1024)),
        sa.Column("text", sa.Text),
        sa.Column("snapshot", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("edited_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("comment", sa.String(512)),
        *_timestamps(),
    )
    op.create_index("ix_news_versions_news_id", "news_versions", ["news_id"])

    # settings
    op.create_table(
        "settings",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", postgresql.JSONB, nullable=False),
        sa.Column("category", sa.String(64), nullable=False, server_default="general"),
        sa.Column("description", sa.Text),
        sa.Column("is_secret", sa.Boolean, nullable=False, server_default=sa.false()),
        *_timestamps(),
    )
    op.create_index("ix_settings_category", "settings", ["category"])

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("actor", sa.String(255)),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(64)),
        sa.Column("entity_id", sa.String(64)),
        sa.Column("changes", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("user_agent", sa.Text),
        *_timestamps(),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])


def downgrade() -> None:
    for table in (
        "audit_logs",
        "settings",
        "news_versions",
        "media_assets",
        "news",
        "channels",
        "source_cities",
        "sources",
        "cities",
        "watermark_profiles",
        "ai_profiles",
        "templates",
        "users",
    ):
        op.drop_table(table)
