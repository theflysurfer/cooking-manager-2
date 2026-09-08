"""Du besoin de recette à une quantité qu'un magasin sait comprendre."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .pantry import Need

MEASURED = "mesure"
COUNTABLE = "comptable"
DOSE = "dose"
UNRESOLVED = "non_resolu"

MEASURED_UNITS = frozenset({"g", "kg", "ml", "cl", "l"})

COUNTABLE_UNITS = frozenset({
    "pièce", "piece", "boîte", "boite", "sachet", "paquet", "pot", "bocal",
    "brique", "botte", "bouquet", "conserve", "barquette", "tranche",
})

DOSE_UNITS = frozenset({
    "c.s.", "c.c.", "pincée", "pincee", "trait", "filet", "goutte", "gousse",
    "poignée", "poignee", "feuille", "branche", "brin", "zeste", "q.s.",
})

PACKAGE = "conditionnement"


@dataclass
class Purchase:
    """Ce qu'il faut commander pour couvrir un besoin."""
    kind: str
    qty: float | None
    unit: str | None
    reason: str


def purchase_for(need: Need, to_buy: float | None = None) -> Purchase | None:
    """Besoin (et reste à acheter) → quantité commandable, ou un refus motivé."""
    quantity = need.qty if to_buy is None else to_buy
    if quantity is not None and quantity <= 0:
        return None

    unit = (need.unit or "").lower()

    if unit in DOSE_UNITS:
        dose = _label(need.qty, need.unit)
        return Purchase(DOSE, 1.0, PACKAGE,
                        f"besoin de {dose} — une dose, pas une quantité d'achat")

    if quantity is None:
        return Purchase(UNRESOLVED, None, need.unit,
                        "aucune quantité dans la fiche — à décider à la main")

    if unit in MEASURED_UNITS:
        return Purchase(MEASURED, quantity, need.unit, "quantité directement commandable")

    if unit in COUNTABLE_UNITS:
        return Purchase(COUNTABLE, float(math.ceil(quantity)), need.unit,
                        "unité déjà commandable")

    if not unit:
        return Purchase(UNRESOLVED, None, None,
                        "aucune unité dans la fiche — à décider à la main")

    return Purchase(UNRESOLVED, None, need.unit,
                    f"unité « {need.unit} » inconnue du convertisseur")


def _label(qty: float | None, unit: str | None) -> str:
    return f"{qty} {unit}".strip() if qty is not None else (unit or "?")
