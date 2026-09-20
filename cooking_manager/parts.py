"""La part d'un convive dont le régime refuse un ingrédient du plat — ADR 0025."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from cooking_manager.ingredients import normalize_name
from cooking_manager.substitutions import IngredientRepair

@dataclass(frozen=True)
class Share:
    """La fraction d'un plat qui part en substitution, et pour qui."""

    diet: str
    convives: tuple[str, ...]
    covers: int

    @property
    def fraction(self) -> float:
        if self.covers <= 0:
            return 0.0
        return min(len(self.convives) / self.covers, 1.0)

def _scaled(value, factor: float):
    return None if value is None else float(value) * factor

def apply_repairs(
    ingredients: Sequence[dict],
    repairs: Sequence[IngredientRepair],
    shares: dict[str, Share],
) -> list[dict]:
    """Découpe une ligne réparée : part d'origine et part substituée — ADR 0025."""
    by_raw: dict[str, list[IngredientRepair]] = {}
    for repair in repairs:
        share = shares.get(repair.diet)
        if share is None or share.fraction <= 0:
            continue
        by_raw.setdefault(repair.ingredient, []).append(repair)

    out: list[dict] = []
    for ing in ingredients:
        raw = str(ing.get("raw") or ing.get("name") or "")
        applicable = by_raw.get(raw) or []
        if not applicable:
            out.append(dict(ing))
            continue

        taken = 0.0
        for repair in applicable:
            share = shares[repair.diet]
            fraction = min(share.fraction, 1.0 - taken)
            if fraction <= 0:
                continue
            taken += fraction
            target = repair.substitution.target
            who = ", ".join(share.convives)
            out.append({
                **ing,
                "name": target,
                "name_normalized": normalize_name(target),
                "qty_min": _scaled(ing.get("qty_min"), fraction),
                "qty_max": _scaled(ing.get("qty_max"), fraction),
                "raw": f"{target} (part de {who})",
                "substituted_for": raw,
                "diet": repair.diet,
            })

        remaining = 1.0 - taken
        if remaining > 0:
            out.append({
                **ing,
                "qty_min": _scaled(ing.get("qty_min"), remaining),
                "qty_max": _scaled(ing.get("qty_max"), remaining),
            })
    return out

def shares_for(convives: Sequence, covers: int) -> dict[str, Share]:
    """Les régimes présents à cette tablée, avec le nombre de personnes qu'ils portent."""
    by_diet: dict[str, list[str]] = {}
    for convive in convives:
        diet = getattr(convive, "diet", "") or ""
        if diet in ("", "standard", "omnivore"):
            continue
        by_diet.setdefault(diet, []).append(convive.name)
    return {
        diet: Share(diet=diet, convives=tuple(names), covers=covers)
        for diet, names in by_diet.items()
    }

def declared_diets(
    ingredients: Sequence[dict],
    convives: Sequence,
) -> set[str]:
    """Les régimes dont la part est DÉJÀ écrite dans la recette — ADR 0025."""
    from cooking_manager.convives import part_for

    texts = [str(i.get("raw") or i.get("name") or "") for i in ingredients]
    covered: set[str] = set()
    for convive in convives:
        diet = getattr(convive, "diet", "") or ""
        if diet in ("", "standard", "omnivore"):
            continue
        if part_for(convive.name, texts) is not None:
            covered.add(diet)
    return covered
