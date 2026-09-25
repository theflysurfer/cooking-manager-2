"""Élire un produit du drive pour une ligne voulue, ou refuser de deviner (#156)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .bans import Ban, find_ban
from .matching import Signals, compare, PROPOSE
from .packaging import split_packaging
from .pantry import _TO_BASE

ELECTED = "elected"
SUBSTITUTED = "substitution"
ASK = "ask"

MENU = "menu"

PACK_TOLERANCE = 0.05

OUT_OF_STOCK = "rupture"
BANNED = "gamme refusée"
OTHER_FOOD = "autre aliment"
OTHER_PACK = "contenant différent"
PACK_UNKNOWN = "contenant voulu inconnu"


@dataclass(frozen=True)
class Wanted:
    """Ce que la liste réclame — `pack_size` absent veut dire inconnu, pas quelconque."""

    label: str
    food: str = ""
    auchan_id: str | None = None
    pack_size: float | None = None
    pack_unit: str | None = None

    @property
    def food_name(self) -> str:
        """L'aliment, jamais le titre commercial : « cabillaud », pas « cabillaud msc »."""
        return self.food or split_packaging(self.label)[0]


@dataclass(frozen=True)
class Offer:
    """Un produit rendu par la recherche du drive."""

    name: str
    product_id: str
    offer_id: str
    auchan_id: str | None = None
    brand: str | None = None
    seller_id: str | None = None
    stock: int = 1


@dataclass(frozen=True)
class Election:
    """Le verdict, son motif, et ce qui a été écarté — jamais un choix muet."""

    verdict: str
    offer: Offer | None
    origin: str | None
    reason: str
    question: str | None = None
    rejected: list[dict] = field(default_factory=list)


def _base(value: float | None, unit: str | None) -> tuple[float, str] | None:
    if value is None:
        return None
    canonical = _TO_BASE.get((unit or "").lower())
    if canonical is None:
        return None
    base_unit, factor = canonical
    return value * factor, base_unit


def _wanted_pack(wanted: Wanted) -> tuple[float, str] | None:
    explicit = _base(wanted.pack_size, wanted.pack_unit)
    if explicit is not None:
        return explicit
    _, pack = split_packaging(wanted.label)
    return _base(pack.size_value, pack.size_unit)


def _same_pack(reference: tuple[float, str], offer_name: str) -> bool:
    _, pack = split_packaging(offer_name)
    measured = _base(pack.size_value, pack.size_unit)
    if measured is None or measured[1] != reference[1] or not reference[0]:
        return False
    return abs(measured[0] - reference[0]) / reference[0] <= PACK_TOLERANCE


def _same_food(wanted: Wanted, offer: Offer) -> bool:
    offer_name, _ = split_packaging(offer.name)
    return compare(Signals(name=offer_name),
                   Signals(name=wanted.food_name)).verdict == PROPOSE


def _question(wanted: Wanted, rejected: list[dict]) -> str:
    if not rejected:
        motif = "aucun produit rendu par la recherche"
    else:
        motif = " ; ".join(f"{r['product']} — {r['why']}" for r in rejected[:3])
    return f"{wanted.label} : {motif}. Je saute, ou tu tranches ?"


def elect(wanted: Wanted, offers: list[Offer], bans: list[Ban]) -> Election:
    """Produit exact, sinon substitution bornée, sinon une question — jamais une devinette."""
    rejected: list[dict] = []
    survivors: list[Offer] = []

    for offer in offers:
        ban = find_ban(offer.name, bans, auchan_id=offer.auchan_id, brand=offer.brand)
        if ban is not None:
            rejected.append({"product": offer.name, "auchan_id": offer.auchan_id,
                             "why": f"{BANNED} ({ban.label})"})
            continue
        if offer.stock is not None and offer.stock <= 0:
            rejected.append({"product": offer.name, "auchan_id": offer.auchan_id,
                             "why": OUT_OF_STOCK})
            continue
        survivors.append(offer)

    wanted_ref = (wanted.auchan_id or "").strip().lower()
    if wanted_ref:
        for offer in survivors:
            if (offer.auchan_id or "").strip().lower() == wanted_ref:
                return Election(ELECTED, offer, MENU,
                                "le produit voulu, disponible et non banni",
                                rejected=rejected)

    reference = _wanted_pack(wanted)
    if reference is None:
        return Election(ASK, None, None, PACK_UNKNOWN,
                        question=_question(wanted, rejected), rejected=rejected)

    candidates = []
    for offer in survivors:
        if not _same_food(wanted, offer):
            rejected.append({"product": offer.name, "auchan_id": offer.auchan_id,
                             "why": OTHER_FOOD})
            continue
        if not _same_pack(reference, offer.name):
            rejected.append({"product": offer.name, "auchan_id": offer.auchan_id,
                             "why": OTHER_PACK})
            continue
        candidates.append(offer)

    if not candidates:
        return Election(ASK, None, None,
                        "aucun produit du même aliment, non banni, au même contenant",
                        question=_question(wanted, rejected), rejected=rejected)

    chosen = candidates[0]
    size, unit = reference
    return Election(
        SUBSTITUTED, chosen, SUBSTITUTED,
        f"même aliment que « {wanted.label} », contenant équivalent "
        f"({_pretty(size)} {unit}), gamme non bannie",
        rejected=rejected,
    )


def _pretty(value: float) -> str:
    return str(int(value)) if value == int(value) else str(round(value, 3))
