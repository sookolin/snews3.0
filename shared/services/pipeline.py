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
from datetime import datetime, timedelta, timezone

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
from shared.services.emoji_guess import guess_emoji
from shared.services.matcher import CityMatcher
from shared.services.media_service import MediaService
from shared.services.settings_service import SettingsService

log = get_logger("pipeline")

#: Markers that indicate a story of general (world/federal) interest, which is
#: allowed through even when it mentions no monitored city.
_WORLD_MARKERS = (
    "в мире", "мировой", "мировая", "оон", "нато", "евросоюз", "еврокомиссия",
    "сша", "китай", "индия", "турция", "германия", "франция", "великобритания",
    "президент россии", "путин", "правительство рф", "госдума", "совфед",
    "центробанк", "курс валют", "нефть brent", "олимпиада", "чемпионат мира",
)


def _looks_like_world_news(
    title: str | None, text: str, markers: tuple[str, ...] = _WORLD_MARKERS
) -> bool:
    """Heuristically decide whether an item is world/federal news.

    Used as an exception to the "must be regionally relevant" rule so that
    genuinely important non-local stories are not silently discarded.
    ``markers`` may be extended with the keywords of the «другие» entry.
    """
    blob = f"{title or ''} {text[:600]}".lower()
    return any(marker in blob for marker in markers)


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
        #: Whether items matching no monitored city are kept as world news.
        #: Loaded per run in :meth:`process_source`.
        self._world_news_enabled = True
        #: World markers in effect for the current run (built-ins + «другие»
        #: keywords). Loaded per run in :meth:`process_source`.
        self._world_markers: tuple[str, ...] = _WORLD_MARKERS

    async def _dedup_config(self) -> DedupConfig:
        cfg = await self.settings_service.get_many("dedup.")
        return DedupConfig(
            simhash_max_distance=int(cfg.get("dedup.simhash_max_distance", 3)),
            text_similarity_threshold=float(cfg.get("dedup.text_similarity_threshold", 0.9)),
            title_similarity_threshold=float(cfg.get("dedup.title_similarity_threshold", 0.72)),
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
        self._world_news_enabled = bool(
            await self.settings_service.get("pipeline.keep_world_news", True)
        )
        # Keywords of the «другие» entry extend the built-in world markers, so
        # operators can tune what counts as world news without code changes.
        bucket = await self._world_bucket()
        extra_markers: tuple[str, ...] = ()
        if bucket is not None:
            extra_markers = tuple(
                kw.lower()
                for kw in ((bucket.keywords or []) + (bucket.extra_keywords or []))
                if kw
            )
        self._world_markers = _WORLD_MARKERS + extra_markers
        dedup = DedupService(self.session, await self._dedup_config())

        # Real-time mode: only ingest genuinely fresh publications. Without this
        # the first run of a feed would import its whole archive at once.
        max_age = int(await self.settings_service.get("pipeline.max_item_age_minutes", 30))
        if max_age > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age)
            fresh: list[ParsedItem] = []
            for item in items:
                published = item.published_at
                if published is None:
                    # No timestamp: accept only if we have seen this feed before
                    # (first run would otherwise pull the entire archive).
                    if source.last_success_at is not None:
                        fresh.append(item)
                    continue
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                if published >= cutoff:
                    fresh.append(item)
            skipped = len(items) - len(fresh)
            if skipped:
                log.debug("stale_items_skipped", source=source_id, skipped=skipped)
            items = fresh

        for item in items:
            try:
                created_ids = await self._process_item(source, item, matcher, dedup, min_score, report)
                for cid in created_ids:
                    report.created += 1
                    report.created_ids.append(cid)
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
        """Active entries that can match news by keywords (real cities only)."""
        result = await self.session.scalars(
            select(City).where(City.is_active.is_(True), City.kind == "city")
        )
        return list(result.all())

    async def _world_bucket(self) -> City | None:
        """The entry world / unmatched news belong to.

        Prefers the explicitly flagged bucket, then any active «другие» entry.
        Returns ``None`` when the operator has not created one — in that case
        unmatched items are dropped instead of landing in a real city's topic.
        """
        bucket = await self.session.scalar(
            select(City)
            .where(City.is_active.is_(True), City.is_world_bucket.is_(True))
            .limit(1)
        )
        if bucket is not None:
            return bucket
        return await self.session.scalar(
            select(City)
            .where(City.is_active.is_(True), City.kind == "other")
            .order_by(City.id)
            .limit(1)
        )

    async def _process_item(
        self,
        source: Source,
        item: ParsedItem,
        matcher: CityMatcher,
        dedup: DedupService,
        min_score: float,
        report: IngestReport,
    ) -> list[int]:
        """Process one parsed item; return IDs of all created News rows.

        When the source is linked to more than one city the item is cloned into
        each of those cities so it can be moderated and published independently
        in the respective channel (e.g. a regional news agency covering several
        cities creates one pending news per city).
        """
        linked_cities = [c for c in source.cities if c.is_active]
        is_world = _looks_like_world_news(item.title, item.text, self._world_markers)

        if linked_cities:
            # All explicitly linked cities receive a copy of the item.
            # keyword matching is skipped — the editorial binding is authoritative.
            target_cities: list[City] = linked_cities
            match_score = 1.0
            matched_keywords: list[str] = []
        else:
            # No city binding — fall back to keyword matching.
            match = matcher.match(item.text, item.title)
            if match.city and match.score >= min_score and match.city.is_active:
                target_cities = [match.city]
                match_score = match.score
                matched_keywords = match.matched_keywords or []
            else:
                # Nothing matched → world/unmatched bucket.
                if not self._world_news_enabled:
                    report.unmatched += 1
                    return []
                bucket = await self._world_bucket()
                if bucket is None:
                    report.unmatched += 1
                    return []
                target_cities = [bucket]
                match_score = 0.0
                matched_keywords = []
                is_world = True

        created_ids: list[int] = []
        for city in target_cities:
            nid = await self._create_for_city(
                source, item, city, dedup, match_score, matched_keywords, is_world, report
            )
            if nid is not None:
                created_ids.append(nid)
        return created_ids

    async def _create_for_city(
        self,
        source: Source,
        item: ParsedItem,
        city: City,
        dedup: DedupService,
        match_score: float,
        matched_keywords: list[str],
        is_world: bool,
        report: IngestReport,
    ) -> int | None:
        """Dedup-check, persist and AI-process a single News row for *city*."""
        # 1) Dedup (per-city: the same story may already exist for this city)
        dedup_result = await dedup.check(
            text=item.text,
            title=item.title,
            url=item.url,
            city_id=city.id,
        )
        if dedup_result.is_duplicate:
            report.duplicates += 1
            log.debug("duplicate_skipped", reason=dedup_result.reason, of=dedup_result.duplicate_of)
            return None

        # Detect a follow-up: strongly similar to a recent published item but
        # not an outright duplicate → publish as a reply to that message.
        follow_up_of = await self._find_follow_up_target(item, city.id)

        # 2) Persist raw news
        # When the source provides no publication timestamp (website parsers,
        # some TG channels) fall back to the current time so the "В источнике"
        # column is never blank — it then shows the ingestion moment which is
        # a close enough approximation for real-time feeds.
        source_published_at = item.published_at or datetime.now(timezone.utc)
        news = News(
            original_title=item.title,
            original_text=item.text,
            original_url=item.url,
            status=NewsStatus.PROCESSING,
            origin=NewsOrigin.PARSER,
            city_id=city.id,
            source_id=source.id,
            content_hash=dedup_result.content_hash,
            simhash=dedup_result.simhash,
            match_score=match_score,
            matched_keywords=matched_keywords,
            source_published_at=source_published_at,
            is_world_news=is_world,
            reply_to_news_id=follow_up_of,
        )
        self.session.add(news)
        await self.session.flush()

        # 3) Download media
        await self._ingest_media(news, item)

        # 4) AI rewrite (best-effort — falls back to original on failure)
        await self._ai_process(news)

        news.status = NewsStatus.PENDING
        await self.session.flush()
        return news.id

    async def _find_follow_up_target(self, item: ParsedItem, city_id: int) -> int | None:
        """Find a recently published news this item continues, if any.

        A follow-up is textually related to an earlier item (shared topic) but
        not similar enough to be a duplicate. We compare against published news
        of the same city from the last 3 days and require a moderate similarity
        band, so unrelated news are never threaded.
        """
        from datetime import timedelta

        from shared.services.text_utils import similarity_ratio

        since = datetime.now(timezone.utc) - timedelta(days=3)
        candidates = (
            await self.session.scalars(
                select(News)
                .where(
                    News.city_id == city_id,
                    News.status == NewsStatus.PUBLISHED,
                    News.created_at >= since,
                    News.published_message_ids != {},
                )
                .order_by(News.created_at.desc())
                .limit(50)
            )
        ).all()

        blob = f"{item.title or ''} {item.text}"
        best_id: int | None = None
        best_score = 0.0
        for other in candidates:
            other_blob = f"{other.original_title or ''} {other.original_text or ''}"
            score = similarity_ratio(blob, other_blob)
            # Related but not duplicate: 0.55–0.85 similarity band.
            if 0.55 <= score < 0.85 and score > best_score:
                best_score = score
                best_id = other.id
        if best_id is not None:
            log.debug("follow_up_detected", target=best_id, score=round(best_score, 3))
        return best_id

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
            # Prefer the AI-picked emoji, fall back to keyword matching.
            news.emoji = result.emoji or guess_emoji(news.title, news.text or "")
            if result.embedding:
                news.embedding = result.embedding
        except Exception as exc:  # noqa: BLE001
            # Graceful degradation: keep original content, publish still possible.
            log.warning("ai_process_failed", news=news.id, error=str(exc))
            news.title = news.original_title
            news.text = news.original_text
            news.error = f"AI: {exc}"[:500]
            # Still pick an emoji locally so posts are not left bare when the
            # AI provider is unavailable (quota, network, misconfiguration).
            if not news.emoji:
                news.emoji = guess_emoji(news.original_title, news.original_text)
        finally:
            news.ai_processed_at = datetime.now(timezone.utc)
