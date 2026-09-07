from __future__ import annotations

from .nutrition import FoodEntry, Macros, match_key

MACRO_FIELDS = ("kcal", "protein", "carbs", "fat")


def base_from_rows(foods: list[dict], products: list[dict]) -> dict[str, FoodEntry]:
    """Lignes `food` et `product` -> index par cle d'appariement, preseance appliquee."""
    index: dict[str, FoodEntry] = {}

    for row in foods:
        entry = _entry(row.get("name") or row.get("key") or "", row, kind="generique",
                       storage_key=str(row.get("key") or ""))
        if entry is not None:
            _keep_best(index, entry)

    for row in products:
        food_key = row.get("food_key")
        if not food_key or row.get("status") != "linked":
            continue
        entry = _entry(row.get("name") or "", row, kind="marque",
                       storage_key=str(food_key))
        if entry is not None:
            _keep_best(index, entry, at=match_key(str(food_key)))

    return index


def _entry(title: str, row: dict, kind: str, storage_key: str) -> FoodEntry | None:
    macros = _macros(row.get("macros_per_100g"))
    if macros is None:
        return None
    return FoodEntry(key=storage_key, title=title, forms={"100g": macros},
                     source=str(row.get("source") or kind), kind=kind,
                     statut="", path="db")


def _macros(value: object) -> Macros | None:
    if not isinstance(value, dict):
        return None
    macros = Macros(**{f: _number(value.get(f)) for f in MACRO_FIELDS})
    if macros.kcal is None and macros.protein is None:
        return None
    return macros


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _keep_best(index: dict[str, FoodEntry], entry: FoodEntry,
               at: str | None = None) -> None:
    key = at if at is not None else match_key(entry.title)
    if not key:
        return
    current = index.get(key)
    if current is None or entry.rank < current.rank:
        index[key] = entry
