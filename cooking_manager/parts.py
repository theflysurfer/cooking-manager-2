"""La part d'un convive dont le régime refuse un ingrédient du plat — ADR 0025."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from cooking_manager.ingredients import normalize_name
from cooking_manager.substitutions import IngredientRepair

@dataclass(frozen=True)
class DeclaredPart:
    """Une part écrite en DONNÉE : pour qui, et quelle ligne elle remplace — #159."""

    person_id: int
    position: int
    replaces_position: int | None
    raw: str

def _field(line, key):
    if isinstance(line, dict):
        return line.get(key)
    return getattr(line, key, None)

class ColumnNotLoaded(LookupError):
    """La requête n'a pas chargé `for_person_id` : son absence se lirait « aucune part » (#159)."""

def declared_parts(ingredients: Sequence) -> list[DeclaredPart]:
    """Les parts de convive d'une recette, lues dans `for_person_id` — jamais dans le texte."""
    out = []
    for line in ingredients or []:
        if isinstance(line, dict) and "for_person_id" not in line:
            raise ColumnNotLoaded(
                "`for_person_id` absent des colonnes chargées : une part non lue se "
                "confondrait avec une part inexistante — élargir le SELECT")
        person_id = _field(line, "for_person_id")
        if person_id is None:
            continue
        out.append(DeclaredPart(
            person_id=int(person_id),
            position=int(_field(line, "position") or 0),
            replaces_position=(int(rp) if (rp := _field(line, "replaces_position")) is not None
                               else None),
            raw=str(_field(line, "raw") or _field(line, "name") or ""),
        ))
    return out

def lines_for_person(ingredients: Sequence, person_id: int | None) -> list:
    """Ce que CETTE personne mange : le plat commun, moins ce que sa part remplace — #159."""
    parts = declared_parts(ingredients)
    mine = [p for p in parts if p.person_id == person_id] if person_id is not None else []
    replaced = {p.replaces_position for p in mine if p.replaces_position is not None}
    my_positions = {p.position for p in mine}
    others = {p.position for p in parts} - my_positions
    return [line for line in ingredients or []
            if int(_field(line, "position") or 0) not in (replaced | others)]

_PART_SEGMENT = re.compile(r"\(([^)]*)\)|—\s*([^—]*)$")
_PART_WORD = re.compile(r"(?<!\w)parts?(?!\w)", re.IGNORECASE)

def _fold_name(text: str) -> str:
    stripped = unicodedata.normalize("NFD", text)
    return "".join(c for c in stripped if unicodedata.category(c) != "Mn").lower()

def undeclared_part(raw: str, for_person_id: int | None, names: dict[str, int]) -> str | None:
    """Un texte qui annonce la part d'un convive CONNU, sans la donnée qui la porte — #159."""
    if for_person_id is not None or not raw:
        return None
    folded = _fold_name(str(raw))
    for match in _PART_SEGMENT.finditer(folded):
        segment = match.group(1) or match.group(2) or ""
        if not _PART_WORD.search(segment):
            continue
        for name in names:
            if _fold_name(name) in segment:
                return (f"part de {name} annoncée en texte sans `for_person_id` : "
                        "une parenthèse ne dit pas pour qui on achète, "
                        "et ne retire rien du plat commun")
    return None

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
    person_ids: dict[str, int] | None = None,
) -> set[str]:
    """Les régimes dont la part est DÉJÀ écrite — via `for_person_id` si `person_ids` (#159)."""
    from cooking_manager.convives import part_for

    covered: set[str] = set()
    if person_ids is not None:
        by_person = {p.person_id for p in declared_parts(ingredients)}
        for convive in convives:
            diet = getattr(convive, "diet", "") or ""
            if diet in ("", "standard", "omnivore"):
                continue
            if person_ids.get(convive.name) in by_person:
                covered.add(diet)
        return covered

    texts = [str(i.get("raw") or i.get("name") or "") for i in ingredients]
    for convive in convives:
        diet = getattr(convive, "diet", "") or ""
        if diet in ("", "standard", "omnivore"):
            continue
        if part_for(convive.name, texts) is not None:
            covered.add(diet)
    return covered
