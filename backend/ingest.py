"""Ingest recipes and menus from Obsidian vault into PostgreSQL."""

from pathlib import Path

from cooking_manager.vault import read_recipes, read_menus
from cooking_manager.normalizer import normalize_recipe, normalize_menu
from .db import get_pool, init_schema


UPSERT_RECIPE = """
INSERT INTO recipe (
    slug, title, status, recipe_type, family, servings,
    total_time_min, prep_time_min, cook_time_min,
    tags, compatible_constraints, sources, appreciated_by,
    applied_substitutions, mediterranean_criteria,
    construction_regime, execution_count, lieu_execution,
    macros_kcal, macros_protein, macros_carbs, macros_fat,
    protein_density, photo_url, created, updated
) VALUES (
    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26
)
ON CONFLICT (slug) DO UPDATE SET
    title=$2, status=$3, recipe_type=$4, family=$5, servings=$6,
    total_time_min=$7, prep_time_min=$8, cook_time_min=$9,
    tags=$10, compatible_constraints=$11, sources=$12, appreciated_by=$13,
    applied_substitutions=$14, mediterranean_criteria=$15,
    construction_regime=$16, execution_count=$17, lieu_execution=$18,
    macros_kcal=$19, macros_protein=$20, macros_carbs=$21, macros_fat=$22,
    protein_density=$23, photo_url=$24, created=$25, updated=$26,
    ingested_at=NOW()
"""

UPSERT_MENU = """
INSERT INTO menu (title, week_start, week_end, configuration, pattern_sport, status, linked_recipes, created, updated)
VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
ON CONFLICT ON CONSTRAINT menu_pkey DO NOTHING
"""


def _parse_date(val):
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val
    from datetime import date
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
        _parse_date(r.get("created")),
        _parse_date(r.get("updated")),
    )


def _menu_row(m: dict) -> tuple:
    return (
        m.get("title", ""),
        _parse_date(m.get("week_start")),
        _parse_date(m.get("week_end")),
        m.get("configuration"),
        m.get("pattern_sport"),
        m.get("status", "proposed"),
        m.get("linked_recipes", []),
        _parse_date(m.get("created")),
        _parse_date(m.get("updated")),
    )


async def ingest(vault_root: Path, dsn: str) -> dict:
    await init_schema(dsn)
    pool = await get_pool(dsn)

    warnings: list[str] = []

    raw_recipes = read_recipes(vault_root)
    recipes = []
    for raw in raw_recipes:
        normalized, warns = normalize_recipe(raw)
        warnings.extend(warns)
        recipes.append(normalized)

    raw_menus = read_menus(vault_root)
    menus = []
    for raw in raw_menus:
        normalized, warns = normalize_menu(raw)
        warnings.extend(warns)
        menus.append(normalized)

    async with pool.acquire() as conn:
        for r in recipes:
            await conn.execute(UPSERT_RECIPE, *_recipe_row(r))

        await conn.execute("DELETE FROM menu")
        for m in menus:
            await conn.execute(UPSERT_MENU, *_menu_row(m))

    return {
        "recipes_ingested": len(recipes),
        "menus_ingested": len(menus),
        "warnings": warnings,
    }


async def run_ingest(vault_root: str, dsn: str) -> dict:
    return await ingest(Path(vault_root), dsn)
