"""Text utilities: normalisation, hashing, similarity, simhash."""

from __future__ import annotations

import hashlib
import re

_WS_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation and collapse whitespace for comparisons."""
    text = text.lower()
    text = _NON_WORD_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def content_hash(text: str) -> str:
    """Return a stable SHA-256 hash of the normalised text."""
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def compute_simhash(text: str) -> int:
    """Compute a 64-bit SimHash of the text for near-duplicate detection."""
    from simhash import Simhash

    tokens = normalize_text(text).split()
    if not tokens:
        return 0
    return int(Simhash(tokens).value)


def hamming_distance(a: int, b: int) -> int:
    """Number of differing bits between two integers."""
    return bin(a ^ b).count("1")


def similarity_ratio(a: str, b: str) -> float:
    """Normalised Levenshtein similarity in [0, 1] via rapidfuzz."""
    from rapidfuzz import fuzz

    return fuzz.token_set_ratio(normalize_text(a), normalize_text(b)) / 100.0


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    import numpy as np

    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0.0:
        return 0.0
    return float(np.dot(va, vb) / denom)
