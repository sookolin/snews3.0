"""Ingestion pipeline — the orchestration heart of the system.

Flow for a source:

    fetch items → for each item:
        match city → dedup check → persist News → download media →
        AI rewrite → mark PENDING → (moderation notification handled by caller)

The pipeline is transport-agnostic: it persists results and returns the created
News ids. The worker layer schedules it and triggers moderation notifications.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.enums import NewsOrigin, NewsStatus
from shared.logging import get_logger
from shared.models.city import City
from shared.models.media import MediaAsset
from shared.models.news import News
from shared.models.source import Source
from shared.plugins.parsers import parser_registry
from shared.plugins.parsers.base import ParsedItem
from shared.services.ai_service import AIService
from shared.services.dedup import DedupConfig, DedupService
from shared.services.matcher import CityMatcher
from shared.services.media_service import MediaService
from shared.services.settings_service import SettingsService

log = get_logger("pipeline")


@dataclass
class IngestReport:
    source_id: int
    fetched: int = 0
    created: int = 0
    duplicates: int = 0
    unmatched: int = 0
    errors: int = 0
    created_ids: list[int] = field(default_factory=list)


class IngestionPipeline:
    """Process a source end-to-end and persist matched, deduped, AI-ready news."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings_service = SettingsService(session)
        self.media_service = MediaService(session)

    async def _dedup_config(self) -> DedupConfig:
        cfg = await self.settings_service.get_many("dedup.")
        return DedupConfig(
            simhash_max_distance=int(cfg.get("dedup.simhash_max_distance", 3)),
            text_similarity_threshold=float(cfg.get("dedup.text_similarity_threshold", 0.9)),
            embedding_threshold=float(cfg.get("dedup.embedding_threshold", 0.92)),
            lookback_days=int(cfg.get("dedup.lookback_days", 14)),
        )

    async def process_source(self, source_id: int) -> IngestReport:
        """Fetch and process a single source."""
        source = await self.session.get(Source, source_id)
        report = IngestReport(source_id=source_id)
        if source is None or not source.is_active:
            return report

        if not parser_registry.has(source.type.value):
            source.last_error = f"No parser for type {source.type}"
            return report

        parser = parser_registry.get(source.type.value)(source)
        source.last_checked_at = datetime.now(timezone.utc)

        try:
            items = await parser.fetch()
        except Exception as exc:  # noqa: BLE001
            source.last_error = str(exc)[:1000]
            source.error_count += 1
            log.error("source_fetch_failed", source=source_id, error=str(exc))
            return report

        source.last_success_at = datetime.now(timezone.utc)
        source.last_error = None
        source.error_count = 0
        report.fetched = len(items)

        # Candidate cities: those explicitly linked to the source, else all active.
        cities = list(source.cities) if source.cities else await self._all_active_cities()
        matcher = CityMatcher(cities)
        min_score = float(await self.settings_service.get("matching.min_score", 0.3))
        dedup = DedupService(self.session, await self._dedup_config())

        for item in items:
            try:
                created = await self._process_item(source, item, matcher, dedup, min_score, report)
                if created is not None:
                    report.created += 1
                    report.created_ids.append(created)
            except Exception as exc:  # noqa: BLE001
                report.errors += 1
                log.error("item_process_failed", source=source_id, error=str(exc))

        await self.session.flush()
        log.info(
            "source_processed",
            source=source_id,
            fetched=report.fetched,
            created=report.created,
            duplicates=report.duplicates,
            unmatched=report.unmatched,
        )
        return report

    async def _all_active_cities(self) -> list[City]:
        result = await self.session.scalars(select(City).where(City.is_active.is_(True)))
        return list(result.all())

    async def _process_item(
        self,
        source: Source,
        item: ParsedItem,
        matcher: CityMatcher,
        dedup: DedupService,
        min_score: float,
        report: IngestReport,
    ) -> int | None:
        # 1) City matching
        match = matcher.match(item.text, item.title)
        matched_city = match.city
        match_score = match.score
        matched_keywords = match.matched_keywords

        # If the source is explicitly bound to cities, its posts belong to those
        # cities directly — keyword matching only picks the best one, and we do
        # not drop items that fail the keyword threshold.
        linked_cities = list(source.cities)
        if linked_cities:
            if matched_city is None or match_score < min_score:
                matched_city = linked_cities[0]
                match_score = max(match_score, 1.0)
                matched_keywords = matched_keywords or []
        elif matched_city is None or match_score < min_score:
            report.unmatched += 1
            return None

        # 2) Dedup
        dedup_result = await dedup.check(
            text=item.text,
            title=item.title,
            url=item.url,
            city_id=matched_city.id,
        )
        if dedup_result.is_duplicate:
            report.duplicates += 1
            log.debug("duplicate_skipped", reason=dedup_result.reason, of=dedup_result.duplicate_of)
            return None

        # 3) Persist raw news
        news = News(
            original_title=item.title,
            original_text=item.text,
            original_url=item.url,
            status=NewsStatus.PROCESSING,
            origin=NewsOrigin.PARSER,
            city_id=matched_city.id,
            source_id=source.id,
            content_hash=dedup_result.content_hash,
            simhash=dedup_result.simhash,
            match_score=match_score,
            matched_keywords=matched_keywords,
        )
        self.session.add(news)
        await self.session.flush()

        # 4) Download media
        await self._ingest_media(news, item)

        # 5) AI rewrite (best-effort — falls back to original on failure)
        await self._ai_process(news)

        news.status = NewsStatus.PENDING
        await self.session.flush()
        return news.id

    async def _ingest_media(self, news: News, item: ParsedItem) -> None:
        for position, media in enumerate(item.media):
            try:
                rel_path, mime, size = await self.media_service.download(
                    media.url, subdir=f"news/{news.id}"
                )
                asset = MediaAsset(
                    news_id=news.id,
                    type=media.type,
                    file_path=rel_path,
                    remote_url=media.url,
                    mime_type=mime,
                    file_size=size,
                    caption=media.caption,
                    position=position,
                )
                self.session.add(asset)
            except Exception as exc:  # noqa: BLE001
                log.warning("media_download_failed", url=media.url, error=str(exc))
        await self.session.flush()

    async def _ai_process(self, news: News) -> None:
        ai_service = AIService(self.session)
        try:
            result, profile = await ai_service.process(news.original_title, news.original_text)
            news.title = result.title or news.original_title
            news.text = result.text or news.original_text
            news.ai_profile_id = profile.id
            if result.embedding:
                news.embedding = result.embedding
        except Exception as exc:  # noqa: BLE001
            # Graceful degradation: keep original content, publish still possible.
            log.warning("ai_process_failed", news=news.id, error=str(exc))
            news.title = news.original_title
            news.text = news.original_text
            news.error = f"AI: {exc}"[:500]
