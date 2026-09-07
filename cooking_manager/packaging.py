"""Séparer ce qu'un aliment EST de la façon dont il est vendu."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .ingredients import UNIT_ALIASES

_UNIT_WORDS = sorted(
    (v for variants in UNIT_ALIASES.values() for v in variants),
    key=len,
    reverse=True,
)
_UNIT_LOOKUP = {v.lower(): canonical
                for canonical, variants in UNIT_ALIASES.items()
                for v in variants}

_PACK_WORDS = ("sachet", "sachets", "boîte", "boîtes", "boite", "boites",
               "paquet", "paquets", "pot", "pots", "brique", "briques",
               "barquette", "barquettes", "bocal", "bocaux")

_COUNT_SUFFIX = re.compile(r"\s*[xX×]\s*(\d+)\s*$")
_LEADING_COUNT = re.compile(
    r"^\s*(\d+)\s+(" + "|".join(_PACK_WORDS) + r")\s+(?:de\s+|d')?",
    re.IGNORECASE,
)
_PACK_SIZE = re.compile(
    r"\s*(?:(" + "|".join(_PACK_WORDS) + r")\s+)?"
    r"(\d+(?:[.,]\d+)?)\s*(" + "|".join(re.escape(u) for u in _UNIT_WORDS) + r")\s*$",
    re.IGNORECASE,
)
_PERCENT = re.compile(r"\d+\s*%")


@dataclass(frozen=True)
class Pack:
    """Comment un aliment est vendu — jamais ce qu'il est."""

    count: float | None = None
    size_value: float | None = None
    size_unit: str | None = None


def split_packaging(name: str) -> tuple[str, Pack]:
    """Nom brut → (nom sans conditionnement, conditionnement lu)."""
    if not name:
        return name, Pack()

    count: float | None = None
    size_value: float | None = None
    size_unit: str | None = None

    rest = name.strip()

    m = _COUNT_SUFFIX.search(rest)
    if m:
        count = float(m.group(1))
        rest = rest[: m.start()].strip()

    m = _LEADING_COUNT.match(rest)
    if m:
        count = float(m.group(1))
        rest = rest[m.end():].strip()

    if not _PERCENT.search(rest):
        m = _PACK_SIZE.search(rest)
        if m and m.group(3).lower() in _UNIT_LOOKUP:
            size_value = float(m.group(2).replace(",", "."))
            size_unit = _UNIT_LOOKUP[m.group(3).lower()]
            if m.group(1):
                count = count or 1.0
            rest = rest[: m.start()].strip()

    return (rest or name.strip()), Pack(count, size_value, size_unit)
