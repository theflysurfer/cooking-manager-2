"""Confronter le panier RÉEL du drive à la liste arrêtée — jamais l'appli à elle-même (#157)."""

from __future__ import annotations

from dataclasses import dataclass, field

MISSING = "MANQUE"
OK = "ok"
SURPLUS = "SURPLUS"
OFF_MENU_ASSUMED = "hors_menu_assume"
OFF_APP = "hors_appli"
UNMEASURABLE = "non_mesurable"

BLOCKING = (MISSING, OFF_APP, UNMEASURABLE)

MANUAL = "manual"

UNREADABLE = "panier Auchan illisible"


@dataclass(frozen=True)
class Need:
    """Ce que la liste arrêtée réclame pour un aliment, dans son unité de base."""

    food: str
    qty: float | None
    unit: str | None
    pack_size: float | None = None


@dataclass(frozen=True)
class CartLine:
    """Une ligne LUE chez le drive. `food` à None = aucune ligne de l'appli ne la porte."""

    label: str
    food: str | None = None
    qty: float | None = None
    unit: str | None = None
    origin: str = ""


@dataclass
class Judgement:
    verdict: str
    need: float | None
    cart: float | None
    unit: str | None
    reason: str = ""
    surplus_measurable: bool = True
    labels: list[str] = field(default_factory=list)


def unreadable(reason: str) -> dict:
    """Une lecture qui n'a pas eu lieu — jamais `ok`, jamais un panier réputé conforme."""
    return {"source": "auchan", "ok": False, "measured": False,
            "reason": f"{UNREADABLE} : {reason}", "counts": {}, "per_food": []}


def _sum_lines(lines: list[CartLine]) -> tuple[float | None, str | None, list[str]]:
    """Le total d'un aliment chez le drive — None dès qu'une ligne n'est pas mesurable."""
    total, unit = 0.0, None
    for line in lines:
        if line.qty is None or not line.unit:
            return None, line.unit, [ln.label for ln in lines]
        if unit is not None and line.unit != unit:
            return None, None, [ln.label for ln in lines]
        unit = line.unit
        total += line.qty
    return total, unit, [ln.label for ln in lines]


def _judge(need: Need | None, lines: list[CartLine]) -> Judgement:
    cart, cart_unit, labels = _sum_lines(lines)

    if need is None:
        assumed = bool(lines) and all(line.origin == MANUAL for line in lines)
        off_app = any(line.food is None for line in lines)
        if off_app:
            return Judgement(OFF_APP, 0.0, cart, cart_unit, labels=labels,
                             reason="présent chez Auchan, absent de toute ligne de "
                                    "l'application — saisi hors de l'appli")
        if assumed:
            return Judgement(OFF_MENU_ASSUMED, 0.0, cart, cart_unit, labels=labels,
                             reason="ligne posée à la main, hors menu assumé")
        return Judgement(OFF_APP, 0.0, cart, cart_unit, labels=labels,
                         reason="aucun repas ne réclame cet aliment et aucune ligne "
                                "ne l'assume")

    if need.qty is None or not need.unit:
        return Judgement(UNMEASURABLE, need.qty, cart, need.unit, labels=labels,
                         reason="la liste ne chiffre pas ce besoin : rien à confronter")
    if cart is None:
        return Judgement(UNMEASURABLE, need.qty, None, need.unit, labels=labels,
                         reason="quantité illisible chez le drive : le contenant d'au "
                                "moins une ligne est inconnu")
    if cart_unit != need.unit:
        return Judgement(UNMEASURABLE, need.qty, cart, need.unit, labels=labels,
                         reason=f"unités incomparables : besoin en {need.unit}, "
                                f"panier en {cart_unit}")

    if cart < need.qty:
        return Judgement(MISSING, need.qty, cart, need.unit, labels=labels,
                         reason="un repas de la semaine n'a pas son ingrédient")

    over = cart - need.qty
    if need.pack_size is None:
        return Judgement(OK, need.qty, cart, need.unit, labels=labels,
                         surplus_measurable=False,
                         reason="aucun contenant connu : le surplus ne se mesure pas")
    if over > need.pack_size:
        return Judgement(SURPLUS, need.qty, cart, need.unit, labels=labels,
                         reason=f"{_pretty(over)} {need.unit} de trop, au-delà d'un "
                                f"contenant de {_pretty(need.pack_size)} {need.unit}")
    return Judgement(OK, need.qty, cart, need.unit, labels=labels)


def verify(needs: list[Need], lines: list[CartLine], read_at: str) -> dict:
    """Le panier lu chez le drive, aliment par aliment. `measured` se lit AVANT `per_food`."""
    by_food: dict[str, list[CartLine]] = {}
    for line in lines:
        by_food.setdefault(line.food or f"?{line.label}", []).append(line)

    wanted = {need.food: need for need in needs if need.food}
    per_food: list[dict] = []
    for food in sorted(set(wanted) | set(by_food)):
        judgement = _judge(wanted.get(food), by_food.get(food, []))
        per_food.append({"food": food, "need": judgement.need, "cart": judgement.cart,
                         "unit": judgement.unit, "verdict": judgement.verdict,
                         "reason": judgement.reason, "labels": judgement.labels,
                         "surplus_measurable": judgement.surplus_measurable})

    counts: dict[str, int] = {}
    for entry in per_food:
        counts[entry["verdict"]] = counts.get(entry["verdict"], 0) + 1
    blocking = [e for e in per_food if e["verdict"] in BLOCKING]
    return {"source": "auchan", "read_at": read_at, "measured": True,
            "ok": not blocking, "reason": "" if not blocking else
            f"{len(blocking)} aliment(s) bloquant(s) : "
            + ", ".join(f"{e['food']} ({e['verdict']})" for e in blocking),
            "counts": counts, "blocking": blocking, "per_food": per_food}


def _pretty(value: float) -> str:
    return str(int(value)) if value == int(value) else str(round(value, 2))
