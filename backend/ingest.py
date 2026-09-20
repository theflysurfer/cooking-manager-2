"""Écrit recettes et menus en PostgreSQL — ADR 0022."""

import json
import logging
from datetime import date
from pathlib import Path

from cooking_manager.ingredients import parse_recipe_body, normalize_name
from .db import get_pool, init_schema

log = logging.getLogger(__name__)

UPSERT_RECIPE = """
INSERT INTO recipe (
    slug, title, status, recipe_type, family, servings,
    total_time_min, prep_time_min, cook_time_min,
    tags, compatible_constraints, sources, appreciated_by,
    applied_substitutions, mediterranean_criteria,
    construction_regime, execution_count, lieu_execution,
    macros_kcal, macros_protein, macros_carbs, macros_fat,
    protein_density, photo_url, sub_recipes, body, created, updated
) VALUES (
    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,
    COALESCE($27, CURRENT_DATE), COALESCE($28, CURRENT_DATE)
)
ON CONFLICT (slug) DO UPDATE SET
    title=$2, status=$3, recipe_type=$4, family=$5, servings=$6,
    total_time_min=$7, prep_time_min=$8, cook_time_min=$9,
    tags=$10, compatible_constraints=$11, sources=$12, appreciated_by=$13,
    applied_substitutions=$14, mediterranean_criteria=$15,
    construction_regime=$16, execution_count=$17, lieu_execution=$18,
    macros_kcal=$19, macros_protein=$20, macros_carbs=$21, macros_fat=$22,
    protein_density=$23, photo_url=COALESCE($24, recipe.photo_url),
    sub_recipes=$25, body=$26,
    created=COALESCE(recipe.created, $27, CURRENT_DATE),
    updated=COALESCE($28, CURRENT_DATE),
    ingested_at=NOW()
"""

UPSERT_MENU = """
INSERT INTO menu (slug, title, week_start, week_end, configuration, pattern_sport, status, linked_recipes, meals, body, created, updated)
VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
ON CONFLICT (slug) DO UPDATE SET
    title=$2, week_start=$3, week_end=$4, configuration=$5, pattern_sport=$6,
    status=$7, linked_recipes=$8, meals=$9, body=$10,
    created=$11, updated=$12,
    ingested_at=NOW()
"""


def _parse_date(val):
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val
    try:
        return date.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


def _recipe_row(r: dict) -> tuple:
    macros = r.get("macros") or {}
    return (
        r.get("slug", ""),
        r.get("title", ""),
        r.get("status", "draft"),
        r.get("recipe_type"),
        r.get("family"),
        r.get("servings"),
        r.get("total_time_min"),
        r.get("prep_time_min"),
        r.get("cook_time_min"),
        r.get("tags", []),
        r.get("compatible_constraints", []),
        r.get("sources", []),
        r.get("appreciated_by", []),
        r.get("applied_substitutions", []),
        [int(x) for x in r.get("mediterranean_criteria", []) if x is not None],
        r.get("construction_regime"),
        r.get("execution_count", 0),
        r.get("lieu_execution"),
        macros.get("kcal"),
        macros.get("protein"),
        macros.get("carbs"),
        macros.get("fat"),
        r.get("protein_density"),
        r.get("photo_url"),
        r.get("sub_recipes", []),
        r.get("_body", ""),
        _parse_date(r.get("created")),
        _parse_date(r.get("updated")),
    )


def _menu_row(m: dict) -> tuple:
    meals = m.get("meals") or m.get("repas")
    return (
        m.get("slug", ""),
        m.get("title", ""),
        _parse_date(m.get("week_start")),
        _parse_date(m.get("week_end")),
        m.get("configuration"),
        m.get("pattern_sport"),
        m.get("status", "proposed"),
        m.get("linked_recipes", []),
        json.dumps(meals) if meals else None,
        m.get("_body", ""),
        _parse_date(m.get("created")),
        _parse_date(m.get("updated")),
    )


async def write_recipe(conn, r: dict) -> tuple[list[str], int, int, int]:
    """Upsert a recipe and (re)parse its body — ADR 0010/0020."""
    warnings: list[str] = []
    if not r.get("photo_url"):
        slug = r.get("slug", "")
        media_dir = Path(__file__).resolve().parent.parent / "web" / "media" / "recipes"
        if slug and (media_dir / f"{slug}.jpg").is_file():
            r["photo_url"] = f"/media/recipes/{slug}.jpg"

    await conn.execute(UPSERT_RECIPE, *_recipe_row(r))

    content = parse_recipe_body(r.get("_body", ""))
    recipe_id = await conn.fetchval(
        "SELECT id FROM recipe WHERE slug = $1", r.get("slug", "")
    )
    if recipe_id is None:
        return warnings, 0, 0, 0

    await conn.execute("DELETE FROM recipe_ingredient WHERE recipe_id = $1", recipe_id)
    for ing in content.ingredients:
        await conn.execute(
            """INSERT INTO recipe_ingredient
               (recipe_id, position, raw, qty_min, qty_max, unit, name,
                name_normalized, is_optional, parsed)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
            recipe_id, ing.position, ing.raw, ing.qty_min, ing.qty_max,
            ing.unit, ing.name, ing.name_normalized, ing.is_optional, ing.parsed,
        )

    await conn.execute("DELETE FROM recipe_step WHERE recipe_id = $1", recipe_id)
    for step in content.steps:
        await conn.execute(
            "INSERT INTO recipe_step (recipe_id, position, text) VALUES ($1,$2,$3)",
            recipe_id, step.position, step.text,
        )

    parsed = sum(1 for i in content.ingredients if i.parsed)
    raw_only = sum(1 for i in content.ingredients if not i.parsed)
    if not content.ingredients:
        warnings.append(
            f"{r.get('slug')}: AUCUN ingrédient parsé — la section "
            "« ## Ingrédients » est absente, vide ou d'un format inattendu"
        )
    elif content.parse_rate < 0.5:
        warnings.append(
            f"{r.get('slug')}: seulement {content.parse_rate:.0%} des ingrédients "
            "structurés — vérifier le format de la section"
        )
    return warnings, parsed, raw_only, len(content.steps)


async def write_menu(conn, m: dict) -> None:
    """Upsert one normalized menu dict. Caller runs _link_meals afterwards."""
    await conn.execute(UPSERT_MENU, *_menu_row(m))


async def relink_meals(dsn: str) -> dict:
    """Re-resolve menu_meal → recipe links. Vault-free replacement for ingest()."""
    await init_schema(dsn)
    pool = await get_pool(dsn)
    async with pool.acquire() as conn:
        linked, orphan = await _link_meals(conn)
    return {"meals_linked": linked, "meals_orphan": orphan}


SLOTS = ("breakfast", "lunch", "snack", "dinner")


async def _link_meals(conn) -> tuple[int, int]:
    """Éclate `menu.meals` (JSONB) en lignes `menu_meal`, recettes résolues."""
    recipes = await conn.fetch("SELECT id, slug, title FROM recipe")
    by_slug = {r["slug"]: r["id"] for r in recipes}
    by_norm = {}
    for r in recipes:
        key = normalize_name(r["title"] or "")
        if key:
            by_norm.setdefault(key, r)

    linked = orphan = 0
    menus = await conn.fetch("SELECT id, meals FROM menu WHERE meals IS NOT NULL")
    for menu in menus:
        meals = menu["meals"]
        if isinstance(meals, str):
            meals = json.loads(meals)
        if not meals:
            continue

        written: list[str] = []

        for position, meal in enumerate(meals, start=1):
            for slot in SLOTS:
                dish = (meal.get(slot) or "").strip()
                if not dish:
                    continue
                if meal.get(slot + "_leftovers"):
                    await conn.execute(
                        """INSERT INTO menu_meal
                             (menu_id, day, day_label, position, slot, dish, match_kind, covers)
                           VALUES ($1,$2,$3,$4,$5,$6,'leftovers',$7)
                           ON CONFLICT (menu_id, position, slot) DO UPDATE SET
                             dish = EXCLUDED.dish, recipe_id = NULL,
                             match_kind = 'leftovers', covers = EXCLUDED.covers""",
                        menu["id"], _as_date(meal.get("date")), meal.get("day"),
                        position, slot, dish, meal.get("covers"),
                    )
                    written.append(f"{position}:{slot}")
                    continue

                explicit = (meal.get(slot + "_slug") or "").strip()
                if explicit:
                    recipe_id, kind = by_slug.get(explicit), "explicit"
                    if recipe_id is None:
                        log.warning("menu %s : slug de recette inconnu %r (%s)",
                                    menu["id"], explicit, dish)
                        kind = "explicit_missing"
                else:
                    recipe_id, kind = _resolve_dish(dish, by_norm)
                if recipe_id is not None:
                    linked += 1
                else:
                    orphan += 1
                await conn.execute(
                    """INSERT INTO menu_meal
                         (menu_id, day, day_label, position, slot, dish, recipe_id, match_kind, covers)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                       ON CONFLICT (menu_id, position, slot) DO UPDATE SET
                         dish = EXCLUDED.dish, recipe_id = EXCLUDED.recipe_id,
                         match_kind = EXCLUDED.match_kind, covers = EXCLUDED.covers""",
                    menu["id"], _as_date(meal.get("date")), meal.get("day"),
                    position, slot, dish,
                    recipe_id, kind, meal.get("covers"),
                )
                written.append(f"{position}:{slot}")

        await conn.execute(
            """DELETE FROM menu_meal
               WHERE menu_id = $1
                 AND (position::text || ':' || slot) <> ALL($2::text[])""",
            menu["id"], written,
        )
    return linked, orphan


def _resolve_dish(dish: str, by_norm: dict) -> tuple[int | None, str | None]:
    """Intitulé de repas → recette, avec le motif d'appariement retenu."""
    norm = normalize_name(dish or "")
    if not norm:
        return None, None
    if norm in by_norm:
        return by_norm[norm]["id"], "exact"
    for key, recipe in by_norm.items():
        if len(key) > 12 and (key in norm or norm.startswith(key)):
            return recipe["id"], "contains"
        if len(norm) > 12 and (norm in key or key.startswith(norm)):
            return recipe["id"], "contained_by"
    return None, None


def _as_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None
