"""Rapprochement : chaque etage propose des candidats, un seul etage refuse."""

from __future__ import annotations

from dataclasses import dataclass

from .nutrition import match_key
from .pantry import STOP_WORDS

SUBJECT_FOOD_KEY = "food_key"
SUBJECT_FOOD_KIND = "food_kind"
SUBJECTS: tuple[str, ...] = (SUBJECT_FOOD_KEY, SUBJECT_FOOD_KIND)

EXACT = "exact"
CONTAINED = "contained"
OVERLAP = "overlap"
QUEUED = "queued"

OVERLAP_FLOOR = 0.45
MAX_CANDIDATES = 8

NO_CANDIDATE = "aucun candidat du referentiel"
COMPOSITE_REFUSED = "produit composite : aucun aliment ne porte ses macros (ADR 0016)"


@dataclass(frozen=True)
class Candidate:
    value: str
    label: str
    score: float
    origin: str

    def as_dict(self) -> dict:
        return {"value": self.value, "label": self.label,
                "score": round(self.score, 3), "origin": self.origin}


@dataclass(frozen=True)
class Proposal:
    decision: str | None
    origin: str
    reason: str
    candidates: tuple[Candidate, ...] = ()

    @property
    def settled(self) -> bool:
        return self.decision is not None

    def as_dict(self) -> dict:
        return {"decision": self.decision, "origin": self.origin, "reason": self.reason,
                "candidates": [c.as_dict() for c in self.candidates]}


def content_words(text: str) -> list[str]:
    """Les mots porteurs : normalises, sans particule ni mot-outil."""
    return [w for w in match_key(text or "").split() if w not in STOP_WORDS]


def _refuse(reason: str, candidates: list[Candidate]) -> Proposal:
    """L'unique etage de refus : rien ne se decide, tout se nomme et se compte."""
    ranked = tuple(sorted(candidates, key=lambda c: (-c.score, c.value))[:MAX_CANDIDATES])
    if not ranked:
        return Proposal(None, QUEUED, reason, ())
    return Proposal(None, QUEUED, f"{reason} ({len(ranked)} candidat(s) a trancher)", ranked)


def _score(label_words: list[str], target_words: list[str]) -> tuple[float, str] | None:
    if not label_words or not target_words:
        return None
    label_set, target_set = set(label_words), set(target_words)
    if label_set == target_set:
        return 1.0, EXACT
    if target_set <= label_set:
        return len(target_set) / len(label_set), CONTAINED
    shared = label_set & target_set
    if not shared:
        return None
    jaccard = len(shared) / len(label_set | target_set)
    return (jaccard, OVERLAP) if jaccard >= OVERLAP_FLOOR else None


def propose_food_key(label: str, foods: dict[str, str],
                     nature: str | None = None) -> Proposal:
    """Un libelle -> une cle d'aliment du referentiel, ou la file. Jamais un aliment neuf."""
    if nature == "composite":
        return Proposal(None, QUEUED, COMPOSITE_REFUSED, ())

    words = content_words(label)
    if not words:
        return _refuse("libelle vide apres normalisation", [])

    candidates: list[Candidate] = []
    exact: list[Candidate] = []
    for key, name in foods.items():
        best: tuple[float, str] | None = None
        for text in (name or "", key):
            scored = _score(words, content_words(text))
            if scored is not None and (best is None or scored[0] > best[0]):
                best = scored
        if best is None:
            continue
        candidate = Candidate(value=key, label=name or key, score=best[0], origin=best[1])
        candidates.append(candidate)
        if best[1] == EXACT:
            exact.append(candidate)

    if len(exact) == 1:
        return Proposal(exact[0].value, EXACT,
                        f"nom normalise identique a « {exact[0].label} »", tuple(exact))
    if len(exact) > 1:
        return _refuse("plusieurs aliments portent le meme nom normalise", exact)
    return _refuse(NO_CANDIDATE if not candidates else "aucun nom identique", candidates)


def propose_food_kind(name: str, category: str | None,
                      kinds: list[dict]) -> Proposal:
    """Un aliment -> une famille fermee du vocabulaire, ou la file. Vide = pas instruit."""
    category_words = content_words(category or "")
    name_words = content_words(name or "")
    if not category_words and not name_words:
        return _refuse("ni nom ni rayon exploitable", [])

    candidates: list[Candidate] = []
    exact: list[Candidate] = []
    for concept in kinds:
        key = str(concept.get("key") or "")
        if not key:
            continue
        terms = [str(concept.get("label") or key), *(concept.get("synonyms") or [])]
        best: tuple[float, str] | None = None
        for term in terms:
            term_words = content_words(term)
            if not term_words:
                continue
            if category_words and set(term_words) == set(category_words):
                best = (1.0, EXACT)
                break
            scored = _score(name_words, term_words)
            if scored is not None and scored[1] != EXACT:
                scored = (scored[0] * 0.9, scored[1])
            if scored is not None and (best is None or scored[0] > best[0]):
                best = scored
        if best is None:
            continue
        candidate = Candidate(value=key, label=str(concept.get("label") or key),
                              score=best[0], origin=best[1])
        candidates.append(candidate)
        if best[1] == EXACT:
            exact.append(candidate)

    if len(exact) == 1:
        dominated = _dominated(exact[0].value, kinds)
        if dominated:
            return _refuse(
                f"« {exact[0].label} » laisse un axe plus fin non tranche",
                [*exact, *dominated])
        return Proposal(exact[0].value, EXACT,
                        f"rayon « {category} » nomme la famille « {exact[0].label} »",
                        tuple(exact))
    if len(exact) > 1:
        return _refuse("plusieurs familles revendiquent ce rayon", exact)
    return _refuse(NO_CANDIDATE if not candidates else "aucune famille certaine", candidates)


def _dominated(key: str, kinds: list[dict]) -> list[Candidate]:
    """Les familles plus fines qu'une famille domine — elle ne tranche jamais a leur place."""
    by_key = {str(c.get("key") or ""): c for c in kinds}
    dominates = [str(k) for k in (by_key.get(key, {}).get("dominates") or [])]
    return [Candidate(value=k, label=str(by_key[k].get("label") or k),
                      score=0.9, origin=CONTAINED)
            for k in dominates if k in by_key]


def link_counts(pending: int | None, settled: int | None) -> dict:
    """`pending` se lit AVANT toute ligne : une file vide n'est pas un referentiel complet."""
    pending, settled = int(pending or 0), int(settled or 0)
    return {"pending": pending, "settled": settled, "total": pending + settled}


def group_by_candidate(entries: list[dict]) -> list[dict]:
    """La file groupee par candidat de tete : les libelles d'une meme chose arrivent ensemble."""
    groups: dict[str, list[dict]] = {}
    for entry in entries:
        candidates = entry.get("candidates") or []
        head = str(candidates[0]["value"]) if candidates else ""
        groups.setdefault(head, []).append(entry)
    return sorted(
        ({"candidate": key or None, "count": len(rows), "entries": rows}
         for key, rows in groups.items()),
        key=lambda g: (-g["count"], g["candidate"] or ""),
    )
