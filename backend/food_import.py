"""Vault `aliments-vérifiés/` → enregistrements food, food_unit et product."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from cooking_manager.food_units import read_food_units
from cooking_manager.ingredients import normalize_name
from cooking_manager.matching import PROPOSE, Signals, compare
from cooking_manager.nutrition import Macros, parse_food_sheet
from cooking_manager.packaging import split_packaging

NEUTRAL_FORMS = ("100g", "100 g", "100ml", "100 ml")

ABSENT_VALUES = ("null", "none", "nan", "-", "n/a", "à compléter", "a completer")


@dataclass
class ImportPlan:
    foods: list[dict] = field(default_factory=list)
    units: list[dict] = field(default_factory=list)
    products: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    collisions: list[dict] = field(default_factory=list)


def build_records(root: Path) -> ImportPlan:
    """Lit le vault et prépare les lignes, sans écrire en base."""
    plan = ImportPlan()
    if not root.is_dir():
        return plan

    for path in sorted(root.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        fm, forms = parse_food_sheet(text)
        title = str(fm.get("title") or path.stem)
        brand = _brand(fm.get("marque"))
        is_branded = ("marques" in path.parts
                      or ("generiques" not in path.parts and brand is not None))
        clean_name, pack = split_packaging(title)

        if not forms:
            plan.skipped.append({"path": str(path), "reason": "aucune macro pour 100 g"})
            continue

        macros = _pick_form(forms)
        if macros is None:
            plan.skipped.append({
                "path": str(path),
                "reason": f"plusieurs formes, aucune neutre : {sorted(forms)}",
            })
            continue

        units = [{"unit": u.unit, "grams": u.grams} for u in read_food_units(text)]

        if is_branded:
            plan.products.append({
                "name": clean_name,
                "brand": brand,
                "pack_count": pack.count,
                "pack_size_value": pack.size_value,
                "pack_size_unit": pack.size_unit,
                "nutriscore": fm.get("nutriscore"),
                "macros_per_100g": macros,
                "food_key": None,
                "status": "a_rapprocher",
                "source": "vault",
                "store_ref": str(fm.get("slug") or path.stem),
                "_units": units,
            })
            continue

        key = normalize_name(clean_name)
        plan.foods.append({
            "key": key,
            "name": clean_name,
            "path": str(path),
            "category": fm.get("categorie"),
            "kind": fm.get("type_produit"),
            "ciqual_code": fm.get("ciqual_code"),
            "macros_per_100g": macros,
            "source": fm.get("source_macros"),
            "verified_at": fm.get("date_maj"),
        })
        for unit in units:
            plan.units.append({"food_key": key, "unit": unit["unit"],
                               "grams": unit["grams"], "source": "fiche"})

    _hold_collisions(plan)
    _link_products(plan)
    return plan


def _hold_collisions(plan: ImportPlan) -> None:
    """Deux fiches pour une même clé : aucune n'est importée, les deux sont nommées."""
    seen: dict[str, list[dict]] = {}
    for food in plan.foods:
        seen.setdefault(food["key"], []).append(food)

    clashing = {key for key, foods in seen.items() if len(foods) > 1}
    if not clashing:
        return

    for key in clashing:
        plan.collisions.append({
            "key": key,
            "sheets": [{"name": f["name"], "path": f["path"],
                        "kcal": (f["macros_per_100g"] or {}).get("kcal")}
                       for f in seen[key]],
        })
    plan.foods[:] = [f for f in plan.foods if f["key"] not in clashing]
    plan.units[:] = [u for u in plan.units if u["food_key"] not in clashing]


def _brand(value) -> str | None:
    """Le frontmatter est lu ligne à ligne : « null » y arrive comme une chaîne."""
    text = str(value or "").strip().strip('"')
    return None if text.lower() in ABSENT_VALUES or not text else text


def _pick_form(forms: dict[str, Macros]) -> dict | None:
    """Une seule forme, ou la forme neutre — jamais la première venue."""
    if len(forms) == 1:
        label = next(iter(forms))
    else:
        neutral = [k for k in forms if k.strip().lower() in NEUTRAL_FORMS]
        if len(neutral) != 1:
            return None
        label = neutral[0]
    return {"form": label, **_as_dict(forms[label])}


def _as_dict(macros: Macros) -> dict:
    return {k: getattr(macros, k) for k in ("kcal", "protein", "carbs", "fat")}


def _link_products(plan: ImportPlan) -> None:
    """Rattache chaque produit à un aliment quand aucun signal ne s'y oppose."""
    by_key = {f["key"]: f for f in plan.foods}
    for product in plan.products:
        candidate = Signals(name=product["name"], grams=product.get("pack_size_value"),
                            brand=product.get("brand"))
        units = product.pop("_units", [])
        for key, food in by_key.items():
            if compare(candidate, Signals(name=food["name"])).verdict != PROPOSE:
                continue
            product["food_key"] = key
            product["status"] = "linked"
            break
        for unit in units:
            plan.units.append({"food_key": product["food_key"], "unit": unit["unit"],
                               "grams": unit["grams"], "source": "produit"})


PERSON_NAMES = ("julien", "clemence", "clémence", "lea", "léa", "titouan", "tabby")

AVERSION_MARKERS = ("pas de", "pas d'", "n'aime", "naime", "deteste", "déteste",
                    "refuse", "allergi", "intoleran", "intolérant", "interdit",
                    "eviter", "éviter", "ne mange pas", "jamais", "sans ")


def build_report(root: Path, rows: list[dict]) -> dict:
    """Compare le vault à ce qui est en base — sans rien corriger."""
    plan = build_records(root)
    by_key = {r["key"]: r for r in rows}

    missing = [f["key"] for f in plan.foods if f["key"] not in by_key]
    mismatch = []
    for food in plan.foods:
        stored = by_key.get(food["key"])
        if not stored:
            continue
        expected = (food["macros_per_100g"] or {}).get("kcal")
        actual = (_as_macros(stored.get("macros_per_100g")) or {}).get("kcal")
        if expected is not None and actual is not None and abs(expected - actual) > 1:
            mismatch.append({"key": food["key"], "vault": expected, "base": actual})

    constraints = []
    for path in sorted(root.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            low = line.lower()
            if (any(name in low for name in PERSON_NAMES)
                    and any(marker in low for marker in AVERSION_MARKERS)):
                constraints.append({"sheet": path.stem, "line": line.strip()})

    return {
        "total_sheets": len(plan.foods) + len(plan.products) + len(plan.skipped),
        "imported": len(by_key),
        "missing": missing,
        "macro_mismatch": mismatch,
        "unlinked_products": [p["name"] for p in plan.products
                              if p["status"] == "a_rapprocher"],
        "person_constraints": constraints,
        "collisions": plan.collisions,
        "skipped": plan.skipped,
    }


def _as_macros(value) -> dict | None:
    if isinstance(value, str):
        return json.loads(value)
    return value


async def write_records(conn, plan: ImportPlan) -> dict:
    """Upsert idempotent : rejouer l'import ne duplique rien."""
    for food in plan.foods:
        await conn.execute(
            """INSERT INTO food (key, name, category, kind, ciqual_code,
                                 macros_per_100g, source, verified_at)
               VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8::date)
               ON CONFLICT (key) DO UPDATE SET
                 name = EXCLUDED.name, category = EXCLUDED.category,
                 kind = EXCLUDED.kind, ciqual_code = EXCLUDED.ciqual_code,
                 macros_per_100g = EXCLUDED.macros_per_100g,
                 source = EXCLUDED.source, verified_at = EXCLUDED.verified_at""",
            food["key"], food["name"], food["category"], food["kind"],
            food["ciqual_code"], json.dumps(food["macros_per_100g"]),
            food["source"], _as_date(food["verified_at"]))

    orphan_units = 0
    for unit in plan.units:
        if not unit["food_key"]:
            orphan_units += 1
            continue
        await conn.execute(
            """INSERT INTO food_unit (food_key, unit, grams, source)
               VALUES ($1,$2,$3,$4)
               ON CONFLICT (food_key, unit) DO UPDATE SET grams = EXCLUDED.grams""",
            unit["food_key"], unit["unit"], unit["grams"], unit["source"])

    for product in plan.products:
        await conn.execute(
            """INSERT INTO product (food_key, name, brand, pack_count,
                                    pack_size_value, pack_size_unit, nutriscore,
                                    macros_per_100g, status, source, store, store_ref)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11,$12)
               ON CONFLICT (store, store_ref) DO UPDATE SET
                 food_key = EXCLUDED.food_key, status = EXCLUDED.status,
                 name = EXCLUDED.name, brand = EXCLUDED.brand,
                 pack_count = EXCLUDED.pack_count,
                 pack_size_value = EXCLUDED.pack_size_value,
                 pack_size_unit = EXCLUDED.pack_size_unit,
                 nutriscore = EXCLUDED.nutriscore,
                 macros_per_100g = EXCLUDED.macros_per_100g""",
            product["food_key"], product["name"], product["brand"],
            product["pack_count"], product["pack_size_value"],
            product["pack_size_unit"], product["nutriscore"],
            json.dumps(product["macros_per_100g"]), product["status"],
            product["source"], "vault", product["store_ref"])

    return {"foods": len(plan.foods),
            "units": len(plan.units) - orphan_units,
            "units_without_food": orphan_units,
            "products": len(plan.products)}


def _as_date(value):
    from datetime import date

    if isinstance(value, date) or value is None:
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None
