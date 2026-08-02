"""City matching service.

Determines which city (if any) a news item belongs to using keyword matching
with morphological normalisation (Russian lemmatisation via pymorphy3),
supplementary keywords and exclusion rules.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass

from shared.logging import get_logger
from shared.models.city import City

log = get_logger("matcher")

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


@functools.lru_cache(maxsize=1)
def _morph():  # type: ignore[no-untyped-def]
    """Return a cached pymorphy3 analyzer, or ``None`` if unavailable."""
    try:
        import pymorphy3

        return pymorphy3.MorphAnalyzer()
    except Exception:  # noqa: BLE001  # pragma: no cover
        return None


# Common Russian inflectional endings, longest first, for the fallback stemmer.
_RU_SUFFIXES = (
    "ами",
    "ями",
    "иями",
    "ого",
    "его",
    "ому",
    "ему",
    "ыми",
    "ими",
    "ах",
    "ях",
    "ов",
    "ев",
    "ей",
    "ий",
    "ый",
    "ой",
    "ая",
    "яя",
    "ое",
    "ее",
    "ым",
    "им",
    "ом",
    "ем",
    "ую",
    "юю",
    "ам",
    "ям",
    "а",
    "я",
    "ы",
    "и",
    "у",
    "ю",
    "е",
    "о",
    "й",
    "ь",
)


def _fallback_stem(word: str) -> str:
    """Crude suffix-stripping stemmer used when pymorphy3 is unavailable."""
    for suffix in _RU_SUFFIXES:
        if len(word) - len(suffix) >= 4 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


@functools.lru_cache(maxsize=100_000)
def _lemma(word: str) -> str:
    """Return the normal form (lemma) of a word, cached.

    Uses pymorphy3 when available; otherwise falls back to a simple Russian
    suffix stemmer so matching still works without the morphology dictionaries.
    """
    analyzer = _morph()
    if analyzer is None:
        return _fallback_stem(word)
    try:
        return analyzer.parse(word)[0].normal_form
    except Exception:  # noqa: BLE001
        return _fallback_stem(word)


def _lemmatize_tokens(text: str) -> set[str]:
    return {_lemma(tok.lower()) for tok in _TOKEN_RE.findall(text.lower())}


@dataclass
class MatchResult:
    city: City | None
    score: float
    matched_keywords: list[str]


class CityMatcher:
    """Match text against a set of cities."""

    def __init__(self, cities: list[City]) -> None:
        self.cities = [c for c in cities if c.is_active]

    def match(self, text: str, title: str | None = None) -> MatchResult:
        """Return the best matching city (or ``None``) for the given text."""
        blob = f"{title or ''}\n{text}"
        tokens = _lemmatize_tokens(blob)
        lowered = blob.lower()

        best: MatchResult = MatchResult(None, 0.0, [])
        for city in self.cities:
            score, matched = self._score_city(city, tokens, lowered)
            if score > best.score:
                best = MatchResult(city, score, matched)

        if best.city is not None:
            log.debug(
                "city_matched",
                city=best.city.id,
                score=round(best.score, 3),
                keywords=best.matched_keywords,
            )
        return best

    def match_all(self, text: str, title: str | None = None, min_score: float = 0.3) -> list[MatchResult]:
        """Every city whose keyword score meets ``min_score``, best first.

        Unlike :meth:`match` (single best city), this supports an item that is
        relevant to several monitored cities at once (e.g. a story naming two of
        them), so the pipeline can target exactly those cities.
        """
        blob = f"{title or ''}\n{text}"
        tokens = _lemmatize_tokens(blob)
        lowered = blob.lower()

        results: list[MatchResult] = []
        for city in self.cities:
            score, matched = self._score_city(city, tokens, lowered)
            if score >= min_score:
                results.append(MatchResult(city, score, matched))
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _score_city(self, city: City, tokens: set[str], lowered: str) -> tuple[float, list[str]]:
        # Exclusions veto the city entirely.
        for excl in city.exclude_keywords:
            if self._contains(excl, tokens, lowered):
                return 0.0, []

        matched: list[str] = []
        primary_hits = 0
        for kw in [city.name, *city.keywords]:
            if self._contains(kw, tokens, lowered):
                matched.append(kw)
                primary_hits += 1

        extra_hits = 0
        for kw in city.extra_keywords:
            if self._contains(kw, tokens, lowered):
                matched.append(kw)
                extra_hits += 1

        if primary_hits == 0 and extra_hits == 0:
            return 0.0, []

        # Weighted score: primary keywords count more than extra ones.
        raw = primary_hits * 1.0 + extra_hits * 0.4
        score = min(1.0, raw / 3.0)
        # A direct city-name mention guarantees a strong score.
        if self._contains(city.name, tokens, lowered):
            score = max(score, 0.75)
        return score, matched

    @staticmethod
    def _contains(keyword: str, tokens: set[str], lowered: str) -> bool:
        keyword = keyword.strip().lower()
        if not keyword:
            return False
        if " " in keyword:
            # Multi-word phrase: substring match on the raw lowered text.
            return keyword in lowered
        return _lemma(keyword) in tokens or keyword in tokens
