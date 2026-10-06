"""Unicode-aware text helpers shared by retrieval and verification."""

from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_SENTENCE_RE = re.compile(r"(?<=[.!?;])\s+|\n+")
_DURATION_RE = re.compile(
    r"\b(\d+)\s*(month|months|year|years|day|days|week|weeks"
    r"|месяц\w*|год\w*|лет|дн\w*|недел\w*)",
    re.IGNORECASE | re.UNICODE,
)

STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "to", "of", "in", "on", "for", "is",
        "are", "may", "be", "by", "with", "as", "at", "it", "this", "that",
        "their", "students", "student", "university",
        "и", "в", "во", "на", "с", "со", "по", "для", "от", "до", "из", "к",
        "что", "как", "это", "или", "не", "а", "но", "у", "о", "об", "за",
        "студент", "студенты", "студентов", "университет",
    }
)

_NEGATIONS = frozenset(
    {
        "not", "no", "never", "cannot", "without", "prohibited", "forbidden",
        "не", "нет", "без", "запрещено", "запрещается", "нельзя",
    }
)
_NEGATION_SUFFIX = ("n't",)


def tokens(text: str) -> list[str]:
    """Lower-cased word and number tokens for any script."""
    return _TOKEN_RE.findall(text.lower())


def keywords(text: str) -> set[str]:
    """Content words; numbers are always kept, short words are dropped."""
    return {
        token
        for token in tokens(text)
        if token not in STOPWORDS and (token.isdigit() or len(token) > 2)
    }


def numbers(text: str) -> set[str]:
    """Normalized numeric values (``1,5`` and ``1.5`` compare equal)."""
    return {match.replace(",", ".") for match in _NUMBER_RE.findall(text)}


def sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_RE.split(text) if part.strip()]


def is_negated(text: str) -> bool:
    words = tokens(text.replace("’", "'"))
    return any(
        word in _NEGATIONS or word.endswith(_NEGATION_SUFFIX) for word in words
    ) or "n't" in text.lower()


def overlap(left: set[str], right: set[str]) -> float:
    """Fraction of *left* present in *right*."""
    if not left:
        return 0.0
    return len(left & right) / len(left)


def duration_hint(text: str) -> str | None:
    match = _DURATION_RE.search(text)
    return match.group(0).lower() if match else None


@dataclass(frozen=True)
class DurationSentence:
    owner: str
    hint: str
    terms: frozenset[str]


def conflicting_durations(items: list[tuple[str, str]]) -> list[str]:
    """Find durations that disagree about the same subject.

    *items* are ``(owner_id, text)`` pairs. Two sentences conflict only when
    they come from different owners, discuss largely the same subject (high
    keyword overlap once numbers are ignored) and state different durations.
    """
    entries: list[DurationSentence] = []
    for owner, text in items:
        for sentence in sentences(text):
            hint = duration_hint(sentence)
            if hint is None:
                continue
            terms = frozenset(
                word for word in keywords(sentence) if not word.isdigit()
            )
            entries.append(DurationSentence(owner, hint, terms))

    conflicts: list[str] = []
    for index, left in enumerate(entries):
        for right in entries[index + 1 :]:
            if left.owner == right.owner or left.hint == right.hint:
                continue
            union = left.terms | right.terms
            if not union:
                continue
            if len(left.terms & right.terms) / len(union) >= 0.5:
                conflicts.append(f"{left.hint} vs {right.hint}")
    return conflicts
