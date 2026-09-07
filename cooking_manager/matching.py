"""Rapprocher deux libellés : un signal peut réfuter seul, aucun ne conclut seul."""

from __future__ import annotations

from dataclasses import dataclass, field

from .ingredients import normalize_name
from .pantry import STOP_WORDS

WEIGHT_RATIO = 5.0
PRICE_RATIO = 10.0

PROPOSE = "propose"
REFUSE = "refuse"
UNSURE = "unsure"


@dataclass(frozen=True)
class Signals:
    name: str
    grams: float | None = None
    price_per_kg: float | None = None
    brand: str | None = None


@dataclass
class Match:
    verdict: str
    reasons: list[str] = field(default_factory=list)


def compare(candidate: Signals, target: Signals) -> Match:
    """Deux jeux de signaux → un verdict motivé."""
    reasons: list[str] = []
    a, b = normalize_name(candidate.name), normalize_name(target.name)

    if not _names_concord(a, b):
        return Match(REFUSE, [f"les noms ne concordent pas : « {a} » / « {b} »"])

    if _refutes(candidate.grams, target.grams, WEIGHT_RATIO):
        reasons.append(f"poids incompatibles : {candidate.grams} g / {target.grams} g")
        return Match(REFUSE, reasons)

    mute = False
    if _is_bogus(candidate.price_per_kg) or _is_bogus(target.price_per_kg):
        reasons.append("prix nul — un parsing manqué, jamais un prix favorable")
        mute = True
    elif _refutes(candidate.price_per_kg, target.price_per_kg, PRICE_RATIO):
        reasons.append(
            f"prix au kilo incompatibles : {candidate.price_per_kg} / {target.price_per_kg}")
        return Match(REFUSE, reasons)

    return Match(UNSURE if mute else PROPOSE, reasons)


def _head_words(text: str) -> list[str]:
    return [w for w in text.split() if w not in STOP_WORDS]


def _names_concord(a: str, b: str) -> bool:
    """Le nom le plus court doit OUVRIR le plus long, pas seulement y figurer."""
    if a == b:
        return True
    short, long = sorted((_head_words(a), _head_words(b)), key=len)
    return bool(short) and long[: len(short)] == short


def _is_bogus(value: float | None) -> bool:
    """Présent mais non positif — une valeur qu'aucune mesure ne produit."""
    return value is not None and value <= 0


def _is_mute(value: float | None) -> bool:
    return value is None or value <= 0


def _refutes(a: float | None, b: float | None, ratio: float) -> bool:
    if _is_mute(a) or _is_mute(b):
        return False
    high, low = max(a, b), min(a, b)  # type: ignore[type-var]
    return high / low >= ratio
