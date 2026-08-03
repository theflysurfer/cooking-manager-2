"""Ingest recipes and menus from Obsidian vault into PostgreSQL."""

import re
import logging
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

from cooking_manager.vault import read_recipes, read_menus
from cooking_manager.normalizer import normalize_recipe, normalize_menu
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
    protein_density, photo_url, body, created, updated
) VALUES (
    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27
)
ON CONFLICT (slug) DO UPDATE SET
    title=$2, status=$3, recipe_type=$4, family=$5, servings=$6,
    total_time_min=$7, prep_time_min=$8, cook_time_min=$9,
    tags=$10, compatible_constraints=$11, sources=$12, appreciated_by=$13,
    applied_substitutions=$14, mediterranean_criteria=$15,
    construction_regime=$16, execution_count=$17, lieu_execution=$18,
    macros_kcal=$19, macros_protein=$20, macros_carbs=$21, macros_fat=$22,
    protein_density=$23, photo_url=$24, body=$25,
    created=$26, updated=$27,
    ingested_at=NOW()
"""

UPSERT_MENU = """
INSERT INTO menu (title, week_start, week_end, configuration, pattern_sport, status, linked_recipes, meals, body, created, updated)
VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
ON CONFLICT ON CONSTRAINT menu_pkey DO NOTHING
"""


_IMAGE_META_PATTERNS = [
    # og:image (both attribute orders)
    (r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE),
    (r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', re.IGNORECASE),
    # twitter:image
    (r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE),
    (r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']', re.IGNORECASE),
    # schema.org Recipe image (JSON-LD)
    (r'"@type"\s*:\s*"Recipe"[^}]*"image"\s*:\s*"([^"]+)"', 0),
    (r'"@type"\s*:\s*"Recipe"[^}]*"image"\s*:\s*\[\s*"([^"]+)"', 0),
]

_MIN_IMG_SIZE = 200


def _scrape_photo(urls: list[str]) -> str | None:
    """Try multiple strategies to find a recipe photo from source URLs."""
    for url in urls[:5]:
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; CookingManager/2.0)"})
            with urlopen(req, timeout=8) as resp:
                html = resp.read(200_000).decode("utf-8", errors="ignore")

            for pattern, flags in _IMAGE_META_PATTERNS:
                m = re.search(pattern, html, flags)
                if m:
                    img_url = m.group(1)
                    if "placeholder" not in img_url.lower():
                        return img_url

            for m in re.finditer(
                r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>',
                html, re.IGNORECASE,
            ):
                tag = m.group(0).lower()
                src = m.group(1)
                if any(skip in src.lower() for skip in ("logo", "icon", "avatar", "sprite", "pixel", "1x1", "data:image/svg", "placeholder")):
                    continue
                w_match = re.search(r'width=["\']?(\d+)', tag)
                h_match = re.search(r'height=["\']?(\d+)', tag)
                if w_match and int(w_match.group(1)) < _MIN_IMG_SIZE:
                    continue
                if h_match and int(h_match.group(1)) < _MIN_IMG_SIZE:
                    continue
                if src.startswith("/"):
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    src = f"{parsed.scheme}://{parsed.netloc}{src}"
                if src.startswith("http"):
                    return src
        except (URLError, OSError, UnicodeDecodeError):
            continue
    return None


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
        r.get("_body", ""),
        _parse_date(r.get("created")),
        _parse_date(r.get("updated")),
    )


def _menu_row(m: dict) -> tuple:
    import json
    meals = m.get("meals") or m.get("repas")
    return (
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

    for r in recipes:
        if not r.get("photo_url") and r.get("sources"):
            photo = _scrape_photo(r["sources"])
            if photo:
                r["photo_url"] = photo
                log.info("Scraped photo for %s: %s", r.get("slug"), photo)

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
