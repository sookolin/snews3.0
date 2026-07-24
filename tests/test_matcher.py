"""Unit tests for the city matcher."""

from __future__ import annotations

from shared.models.city import City
from shared.services.matcher import CityMatcher


def _city(**kwargs) -> City:  # type: ignore[no-untyped-def]
    defaults = dict(
        id=1,
        name="Казань",
        slug="kazan",
        keywords=[],
        extra_keywords=[],
        exclude_keywords=[],
        is_active=True,
        language="ru",
    )
    defaults.update(kwargs)
    return City(**defaults)


def test_matches_city_by_name() -> None:
    matcher = CityMatcher([_city()])
    result = matcher.match("Сегодня в Казани открыли новую станцию метро.")
    assert result.city is not None
    assert result.city.name == "Казань"
    assert result.score >= 0.7


def test_no_match_for_unrelated_text() -> None:
    matcher = CityMatcher([_city()])
    result = matcher.match("Курс валют вырос на бирже сегодня утром.")
    assert result.city is None


def test_exclusion_keyword_vetoes_match() -> None:
    matcher = CityMatcher([_city(exclude_keywords=["спорт"])])
    result = matcher.match("В Казани прошёл спорт турнир", None)
    assert result.city is None


def test_extra_keywords_contribute() -> None:
    city = _city(name="Иннополис", keywords=["иннополис"], extra_keywords=["университет"])
    matcher = CityMatcher([city])
    result = matcher.match("В Иннополисе новый университет открылся")
    assert result.city is not None
    assert "университет" in result.matched_keywords or "иннополис" in [
        k.lower() for k in result.matched_keywords
    ]
