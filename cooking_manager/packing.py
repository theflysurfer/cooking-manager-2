"""Le contenant : combien de paquets couvrent un achat, et quand on l'ignore — ADR 0038."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .pantry import _TO_BASE
from .purchase import DOSE, Purchase, UNRESOLVED


@dataclass(frozen=True)
class PackPlan:
    """Le conditionnement d'un achat — `pack_known: false` quand il n'est pas connu."""

    packs: int | None
    buys: float | None
    unit: str | None
    pack_known: bool
    pack_size: float | None
    reason: str
    surplus: float | None

    @property
    def surplus_packs(self) -> float | None:
        """Le surplus en CONTENANTS : un ratio ferait passer une gousse pour une tête."""
        if self.surplus is None or not self.pack_size:
            return None
        return self.surplus / self.pack_size


def _unknown(reason: str, unit: str | None = None) -> PackPlan:
    return PackPlan(packs=None, buys=None, unit=unit, pack_known=False,
                    pack_size=None, reason=reason, surplus=None)


def _base(value: float, unit: str | None) -> tuple[float, str] | None:
    canonical = _TO_BASE.get((unit or "").lower())
    if canonical is None:
        return None
    base_unit, factor = canonical
    return value * factor, base_unit


def pack_sizes(products: Sequence[dict], unit: str | None) -> list[float]:
    """Les contenants connus pour cet aliment, ramenés à l'unité de l'achat."""
    wanted = _base(1.0, unit)
    if wanted is None:
        return []
    _, wanted_unit = wanted
    sizes = []
    for product in products or []:
        value = product.get("pack_size_value")
        if not value or value <= 0:
            continue
        converted = _base(float(value), product.get("pack_size_unit"))
        if converted is None or converted[1] != wanted_unit:
            continue
        count = product.get("pack_count") or 1.0
        sizes.append(converted[0] * float(count))
    return sorted(sizes)


def pack_plan(purchase: Purchase | None, products: Sequence[dict]) -> PackPlan:
    """Achat + produits connus → nombre de contenants, ou le motif de l'ignorance."""
    if purchase is None:
        return _unknown("aucun achat à conditionner")
    if purchase.kind == DOSE:
        return _unknown("une dose ne s'achète pas au contenant", purchase.unit)
    if purchase.kind == UNRESOLVED or purchase.qty is None:
        return _unknown("aucune quantité à couvrir : le contenant ne se compte pas",
                        purchase.unit)

    scale = _base(1.0, purchase.unit)
    if scale is None:
        return _unknown(f"unité « {purchase.unit} » hors du convertisseur", purchase.unit)

    sizes = pack_sizes(products, purchase.unit)
    if not sizes:
        return _unknown("aucun conditionnement connu pour cet aliment, dans une unité "
                        "comparable à l'achat", purchase.unit)

    per_pack_base = sizes[0]
    needed_base, _ = _base(float(purchase.qty), purchase.unit) or (0.0, "")
    packs = max(1, math.ceil(needed_base / per_pack_base))
    bought_base = packs * per_pack_base

    to_wanted = scale[0]
    pack_size = per_pack_base / to_wanted
    buys = bought_base / to_wanted
    return PackPlan(
        packs=packs,
        buys=round(buys, 3),
        unit=purchase.unit,
        pack_known=True,
        pack_size=round(pack_size, 3),
        reason=f"{packs} × {_pretty(pack_size)} {purchase.unit}",
        surplus=round((bought_base - needed_base) / to_wanted, 3),
    )


def _pretty(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)
