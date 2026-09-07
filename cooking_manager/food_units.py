"""Les unités dans lesquelles un aliment se compte, avec leur poids."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .ingredients import UNIT_ALIASES, normalize_name

_UNIT_LOOKUP = {v.lower(): canonical
                for canonical, variants in UNIT_ALIASES.items()
                for v in variants}

_COUNTED_AS_PIECE = ("oeuf", "œuf", "unite", "unité", "fruit", "piece", "pièce")

_SECTION = re.compile(
    r"^##\s+Par\s+([^(\n]+?)\s*\(\s*~?\s*(\d+(?:[.,]\d+)?)\s*(g|kg|ml|cl|l)\s*\)",
    re.IGNORECASE | re.MULTILINE,
)

_TO_GRAMS = {"g": 1.0, "kg": 1000.0, "ml": 1.0, "cl": 10.0, "l": 1000.0}


@dataclass(frozen=True)
class FoodUnit:
    unit: str
    grams: float


def read_food_units(text: str) -> list[FoodUnit]:
    """Fiche markdown → unités d'usage nommées, avec leur poids."""
    units: list[FoodUnit] = []
    for label, value, unit in _SECTION.findall(text or ""):
        grams = float(value.replace(",", ".")) * _TO_GRAMS[unit.lower()]
        units.append(FoodUnit(_canonical_unit(label), grams))
    return units


def _canonical_unit(label: str) -> str:
    key = normalize_name(label.strip())
    if key in _UNIT_LOOKUP:
        return _UNIT_LOOKUP[key]
    if any(word in key for word in _COUNTED_AS_PIECE):
        return "pièce"
    return key
