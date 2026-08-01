"""Deduplication service.

Combines multiple signals to decide whether a candidate news item duplicates an
already-stored one:

* exact content hash
* URL / title equality
* SimHash Hamming distance (near-duplicate)
* Levenshtein token-set similarity
* embedding cosine similarity (semantic)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.logging import get_logger
from shared.models.news import News
from shared.services.text_utils import (
    compute_simhash,
    content_hash,
    cosine_similarity,
    hamming_distance,
    similarity_ratio,
)

log = get_logger("dedup")


@dataclass
class DedupConfig:
    """Thresholds for the various duplicate signals."""

    simhash_max_distance: int = 3
    text_similarity_threshold: float = 0.9
    #: Headline similarity above which two items are the same story even when
    #: they come from different outlets with different wording.
    title_similarity_threshold: float = 0.72
    embedding_threshold: float = 0.92
    lookback_days: int = 14


@dataclass
class DedupResult:
    is_duplicate: bool
    duplicate_of: int | None = None
    reason: str | None = None
    content_hash: str = ""
    simhash: int = 0


class DedupService:
    """Detect duplicate news items within a lookback window."""

    def __init__(self, session: AsyncSession, config: DedupConfig | None = None) -> None:
        self.session = session
        self.config = config or DedupConfig()

    async def check(
        self,
        text: str,
        title: str | None = None,
        url: str | None = None,
        embedding: list[float] | None = None,
        city_id: int | None = None,
        scope_city: bool = False,
    ) -> DedupResult:
        """Return whether the item duplicates an existing one.

        By default the comparison is global: the same story is often picked up
        by several outlets and matched to different cities, so a global check
        catches cross-source duplicates.

        When ``scope_city`` is ``True`` the comparison is restricted to
        ``city_id``. This is used when one source is editorially bound to
        several cities and the same item is intentionally cloned into each of
        them (e.g. a regional agency covering the whole oblast): those copies
        must not dedup against one another, only against prior items of the
        *same* city.
        """
        chash = content_hash((title or "") + " " + text)
        shash = compute_simhash((title or "") + " " + text)

        since = datetime.now(timezone.utc) - timedelta(days=self.config.lookback_days)

        # When scoping to a city, every comparison is narrowed to that city so
        # multi-city clones of the same source item stay independent.
        def _scoped(stmt):  # type: ignore[no-untyped-def]
            if scope_city and city_id is not None:
                return stmt.where(News.city_id == city_id)
            return stmt

        # 1) Exact hash match (fast, indexed).
        exact = await self.session.scalar(
            _scoped(select(News.id).where(News.content_hash == chash)).limit(1)
        )
        if exact is not None:
            return DedupResult(True, exact, "content_hash", chash, shash)

        # 2) Exact URL match.
        if url:
            by_url = await self.session.scalar(
                _scoped(select(News.id).where(News.original_url == url)).limit(1)
            )
            if by_url is not None:
                return DedupResult(True, by_url, "url", chash, shash)

        # 3) Fuzzy signals against recent items.
        #
        # Global by default (see docstring); narrowed to the city only when
        # ``scope_city`` is set for intentional multi-city clones.
        stmt = _scoped(
            select(News)
            .where(News.created_at >= since)
            .order_by(News.created_at.desc())
            .limit(500)
        )
        recent = (await self.session.scalars(stmt)).all()

        for other in recent:
            other_blob = (other.original_title or "") + " " + (other.original_text or "")

            if (
                other.simhash is not None
                and shash
                and hamming_distance(shash, other.simhash) <= self.config.simhash_max_distance
            ):
                return DedupResult(True, other.id, "simhash", chash, shash)

            if title and other.original_title and title.strip() == other.original_title.strip():
                return DedupResult(True, other.id, "title", chash, shash)

            # Same story published by two different outlets: the wording differs
            # but the headline stays close. Compare headlines separately with a
            # dedicated threshold, otherwise long bodies dilute the similarity.
            if title and other.original_title:
                title_score = similarity_ratio(title, other.original_title)
                if title_score >= self.config.title_similarity_threshold:
                    return DedupResult(True, other.id, "title_similarity", chash, shash)

            if similarity_ratio(text, other_blob) >= self.config.text_similarity_threshold:
                return DedupResult(True, other.id, "text_similarity", chash, shash)

            if (
                embedding
                and other.embedding
                and cosine_similarity(embedding, other.embedding) >= self.config.embedding_threshold
            ):
                return DedupResult(True, other.id, "embedding", chash, shash)

        return DedupResult(False, None, None, chash, shash)
