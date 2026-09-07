"""Conversion d'un retour de table en texte libre vers les trois axes du vocabulaire."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from cooking_manager.substitutions import (
    fold,
    keyword_pattern,
    load_vocabulary,
)

APPRECIATION_FACET = "appreciations"
VERDICT_FACET = "replay_verdicts"
ISSUE_FACET = "issue_kinds"

FEEDBACK_FACETS: tuple[str, ...] = (APPRECIATION_FACET, VERDICT_FACET, ISSUE_FACET)

_APOSTROPHES = str.maketrans({"’": "'", "ʼ": "'"})


class UnknownConcept(ValueError):
    """Une clé proposée n'existe pas dans la facette visée."""


@lru_cache(maxsize=None)
def _facet_patterns(facet: str) -> tuple[tuple[str, str, re.Pattern[str]], ...]:
    vocabulary = load_vocabulary()
    return tuple(
        (concept["key"], synonym, keyword_pattern(synonym))
        for concept in vocabulary[facet]
        for synonym in concept["synonyms"]
    )


@lru_cache(maxsize=None)
def facet_keys(facet: str) -> frozenset[str]:
    return frozenset(concept["key"] for concept in load_vocabulary()[facet])


def normalize_verbatim(text: str) -> str:
    return fold(text.translate(_APOSTROPHES))


def _matches(facet: str, text: str) -> dict[str, int]:
    """Pour chaque clé touchée, la longueur du plus long synonyme reconnu."""
    folded = normalize_verbatim(text)
    found: dict[str, int] = {}
    for key, synonym, pattern in _facet_patterns(facet):
        if pattern.search(folded):
            found[key] = max(found.get(key, 0), len(synonym))
    return found


@dataclass(frozen=True)
class Reading:
    """Ce que le texte libre a effectivement dit — jamais ce qu'il aurait pu vouloir dire."""

    appreciation: str | None = None
    verdict: str | None = None
    issue_kinds: tuple[str, ...] = ()
    ambiguous: dict[str, tuple[str, ...]] = field(default_factory=dict)
    unmatched: tuple[str, ...] = ()


def _read_single(facet: str, text: str) -> tuple[str | None, tuple[str, ...]]:
    """Le synonyme le plus long tranche ; une égalité entre clés reste une ambiguïté."""
    found = _matches(facet, text)
    if not found:
        return None, ()
    best = max(found.values())
    winners = sorted(key for key, length in found.items() if length == best)
    if len(winners) > 1:
        return None, tuple(winners)
    return winners[0], ()


def interpret(text: str) -> Reading:
    """Lit les trois axes d'un retour libre. Ce qui n'est pas dit reste vide."""
    ambiguous: dict[str, tuple[str, ...]] = {}
    unmatched: list[str] = []

    appreciation, appreciation_tie = _read_single(APPRECIATION_FACET, text)
    if appreciation_tie:
        ambiguous[APPRECIATION_FACET] = appreciation_tie
    elif appreciation is None:
        unmatched.append(APPRECIATION_FACET)

    verdict, verdict_tie = _read_single(VERDICT_FACET, text)
    if verdict_tie:
        ambiguous[VERDICT_FACET] = verdict_tie
    elif verdict is None:
        unmatched.append(VERDICT_FACET)

    issues = tuple(sorted(_matches(ISSUE_FACET, text)))
    if not issues:
        unmatched.append(ISSUE_FACET)

    return Reading(
        appreciation=appreciation,
        verdict=verdict,
        issue_kinds=issues,
        ambiguous=ambiguous,
        unmatched=tuple(unmatched),
    )


def validate_concept(facet: str, key: str) -> str:
    if key not in facet_keys(facet):
        raise UnknownConcept(f"{key!r} n'est pas une clé de {facet}")
    return key
