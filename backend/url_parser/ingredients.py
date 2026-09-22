from __future__ import annotations

import re
import unicodedata

from backend.url_parser.models import Ingredient
from backend.url_parser.units import UNIT_LOOKUP, UNIT_PATTERN, expand_fractions

_QTY = r"(?:~|env\.?\s*)?(\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?)(?:\s*[-–—]\s*(\d+(?:[.,]\d+)?))?"

_INGREDIENT_RE = re.compile(
    rf"^\s*{_QTY}\s*(?:({UNIT_PATTERN})(?!\w))?\s*(?:de\s+|d'|du\s+|des\s+|of\s+)?(.*)$",
    re.IGNORECASE,
)

_OPTIONAL_RE = re.compile(
    r"\boptionnel(?:le)?\b|\bfacultatif\b|\bau choix\b|\boptional\b",
    re.IGNORECASE,
)

_LIGATURES = str.maketrans({"œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE"})


def _to_float(raw: str | None) -> float | None:
    if not raw:
        return None
    value = raw.replace(",", ".").strip()
    if "/" in value:
        try:
            num, den = (p.strip() for p in value.split("/", 1))
            return round(float(num) / float(den), 4)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(value)
    except ValueError:
        return None


def _display_name(name: str | None) -> str:
    text = re.sub(r"\s+[–—]\s+.*$", "", name or "")
    text = re.sub(r"[*_`]", "", text)
    return text.strip(" .,;")


def normalize_name(name: str) -> str:
    text = re.sub(r"\([^)]*\)", " ", name)
    text = re.sub(r"\s+[-–—]\s+.*$", "", text)
    text = text.translate(_LIGATURES)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"\b(bio|nature|en poudre|premium|label rouge|aop|igp|organic|fresh)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def parse_ingredient(raw: str, position: int) -> Ingredient:
    text = raw.strip().lstrip("-*+ ").strip()
    ing = Ingredient(position=position, raw=text)
    ing.is_optional = bool(_OPTIONAL_RE.search(text))

    clean = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    clean = expand_fractions(clean)

    m = _INGREDIENT_RE.match(clean)
    if not m:
        ing.name = clean
        return ing

    qty_min, qty_max, unit, name = m.groups()
    ing.quantity = _to_float(qty_min)
    ing.quantity_max = _to_float(qty_max) if qty_max else ing.quantity
    ing.unit = UNIT_LOOKUP.get((unit or "").lower()) if unit else None
    ing.name = _display_name(name)

    if ing.quantity is not None and ing.unit is None and ing.name:
        ing.unit = "pièce"

    ing.parsed = ing.quantity is not None and bool(ing.name)
    if not ing.name:
        ing.name = clean
        ing.parsed = False
    return ing
