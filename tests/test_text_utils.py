"""Unit tests for text utilities and dedup fingerprints."""

from __future__ import annotations

from shared.services.text_utils import (
    compute_simhash,
    content_hash,
    cosine_similarity,
    hamming_distance,
    normalize_text,
    similarity_ratio,
)


def test_normalize_text() -> None:
    assert normalize_text("  Привет, МИР!!!  ") == "привет мир"


def test_content_hash_stable_and_normalised() -> None:
    assert content_hash("Hello, World!") == content_hash("hello world")
    assert content_hash("a") != content_hash("b")


def test_simhash_near_duplicate() -> None:
    text = "В городе торжественно открыли новый большой парк для жителей района"
    near = text + " сегодня утром"
    far = "Совершенно другая новость про экономику и курс валют на бирже"
    a, b, c = compute_simhash(text), compute_simhash(near), compute_simhash(far)
    # Near-duplicate must be closer than an unrelated text.
    assert hamming_distance(a, b) < hamming_distance(a, c)


def test_similarity_ratio() -> None:
    assert similarity_ratio("новый парк открыли", "открыли новый парк") > 0.9
    assert similarity_ratio("погода солнечная", "авария на дороге") < 0.5


def test_cosine_similarity() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
