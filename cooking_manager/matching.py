"""Rapprocher deux libellés : un signal peut réfuter seul, aucun ne conclut seul."""

from __future__ import annotations


from dataclasses import dataclass, field

from .ingredients import normalize_name
from .pantry import STOP_WORDS


def food_link_counts(linked: int | None, total: int | None) -> dict:
    """Rattachement a un aliment : `unlinked` se lit AVANT toute ligne (ADR 0032)."""
    total = int(total or 0)
    linked = int(linked or 0)
    if linked > total:
        raise ValueError(f"linked ({linked}) depasse total ({total})")
    return {"linked": linked, "unlinked": total - linked, "total": total}

WEIGHT_RATIO = 5.0
PRICE_RATIO = 10.0

ABSENT_VALUES = ("null", "none", "nan", "-", "n/a", "à compléter", "a completer")

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


def strip_brand(name: str, brand: str | None) -> str:
    """Le nom sans la marque qu'il répète — elle vit déjà dans `product.brand`."""
    if not brand:
        return name
    words = normalize_name(brand).split()
    remaining = normalize_name(name).split()
    while words and remaining and remaining[0] == words[0]:
        remaining.pop(0)
        words.pop(0)
    return " ".join(remaining) if remaining else name


def _facet_keys(facet: str) -> tuple[str, ...]:
    """Les clés d'une facette du vocabulaire épinglé — jamais une liste écrite ici."""
    from .substitutions import load_vocabulary

    return tuple(c["key"] for c in load_vocabulary().get(facet) or [])


def _clean_against(value: object, facet: str, noun: str, origin: str) -> str | None:
    """Une valeur absente reste absente ; une valeur inventée est refusée."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text in ABSENT_VALUES:
        return None
    allowed = _facet_keys(facet)
    if text not in allowed:
        raise ValueError(
            f"{origin} : {noun} {text!r} inconnu(e) du vocabulaire, attendu parmi {list(allowed)}."
        )
    return text


def product_natures() -> tuple[str, ...]:
    return _facet_keys("product_natures")


def food_kinds() -> tuple[str, ...]:
    return _facet_keys("food_kinds")


def clean_nature(value: object, origin: str = "") -> str | None:
    return _clean_against(value, "product_natures", "nature", origin)


def clean_kind(value: object, origin: str = "") -> str | None:
    return _clean_against(value, "food_kinds", "famille d'aliment", origin)


def link_food_key(product: Signals, nature: str | None,
                  foods: dict[str, str]) -> str | None:
    """Clé d'aliment rattachable, ou None. Un composite n'est JAMAIS rattaché."""
    if nature == "composite":
        return None
    for key, name in foods.items():
        if compare(product, Signals(name=name)).verdict == PROPOSE:
            return key
    return None


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
