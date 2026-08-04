"""Ingest recipes and menus from Obsidian vault into PostgreSQL."""

import asyncio
import json
import re
import logging
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError

from cooking_manager.vault import read_recipes, read_menus, read_convives
from cooking_manager.normalizer import normalize_recipe, normalize_menu
from cooking_manager.ingredients import parse_recipe_body, normalize_name
from cooking_manager.convives import parse_convives
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
INSERT INTO menu (slug, title, week_start, week_end, configuration, pattern_sport, status, linked_recipes, meals, body, created, updated)
VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
ON CONFLICT (slug) DO UPDATE SET
    title=$2, week_start=$3, week_end=$4, configuration=$5, pattern_sport=$6,
    status=$7, linked_recipes=$8, meals=$9, body=$10,
    created=$11, updated=$12,
    ingested_at=NOW()
"""


_IMAGE_META_PATTERNS = [
    re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', re.IGNORECASE),
    re.compile(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']', re.IGNORECASE),
    re.compile(r'"@type"\s*:\s*"Recipe"[^}]*"image"\s*:\s*"([^"]+)"'),
    re.compile(r'"@type"\s*:\s*"Recipe"[^}]*"image"\s*:\s*\[\s*"([^"]+)"'),
]

_RE_IMG_TAG = re.compile(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
_RE_WIDTH = re.compile(r'width=["\']?(\d+)')
_RE_HEIGHT = re.compile(r'height=["\']?(\d+)')
_SKIP_KEYWORDS = ("logo", "icon", "avatar", "sprite", "pixel", "1x1", "data:image/svg", "placeholder")
_MIN_IMG_SIZE = 200


def _scrape_photo(urls: list[str]) -> str | None:
    """Try multiple strategies to find a recipe photo from source URLs."""
    for url in urls[:5]:
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; CookingManager/2.0)"})
            with urlopen(req, timeout=8) as resp:
                html = resp.read(200_000).decode("utf-8", errors="ignore")

            for pat in _IMAGE_META_PATTERNS:
                m = pat.search(html)
                if m:
                    img_url = m.group(1)
                    if "placeholder" not in img_url.lower():
                        return img_url

            for m in _RE_IMG_TAG.finditer(html):
                tag = m.group(0).lower()
                src = m.group(1)
                if any(skip in src.lower() for skip in _SKIP_KEYWORDS):
                    continue
                w_match = _RE_WIDTH.search(tag)
                h_match = _RE_HEIGHT.search(tag)
                if w_match and int(w_match.group(1)) < _MIN_IMG_SIZE:
                    continue
                if h_match and int(h_match.group(1)) < _MIN_IMG_SIZE:
                    continue
                if src.startswith("/"):
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

    convives = parse_convives(read_convives(vault_root).get("_body", ""))
    if not convives:
        warnings.append("aucun convive lu depuis Convives.md — le contrôle de "
                        "compatibilité alimentaire ne pourra rien vérifier")

    # Photos générées : rattachement déterministe par slug. Rien n'est écrit dans
    # le vault, et la liaison survit à chaque ré-ingestion. Priorité au fichier
    # local sur le scraping, qui reste le repli pour les recettes issues du web.
    media_dir = Path(__file__).resolve().parent.parent / "web" / "media" / "recipes"
    photos_linked = 0
    for r in recipes:
        if r.get("photo_url"):
            continue
        slug = r.get("slug", "")
        if slug and (media_dir / f"{slug}.jpg").is_file():
            r["photo_url"] = f"/media/recipes/{slug}.jpg"
            photos_linked += 1

    need_photo = [r for r in recipes if not r.get("photo_url") and r.get("sources")]
    if need_photo:
        results = await asyncio.gather(
            *(asyncio.to_thread(_scrape_photo, r["sources"]) for r in need_photo)
        )
        for r, photo in zip(need_photo, results, strict=True):
            if photo:
                r["photo_url"] = photo
                log.info("Scraped photo for %s: %s", r.get("slug"), photo)

    parsed_ingredients = parsed_steps = 0
    unparsed_lines = 0

    async with pool.acquire() as conn:
        for r in recipes:
            await conn.execute(UPSERT_RECIPE, *_recipe_row(r))

            # Ingrédients et étapes structurés depuis le corps markdown.
            # Remplacement complet à chaque ingestion : le vault fait foi, et les
            # positions changent dès qu'on réordonne une liste.
            content = parse_recipe_body(r.get("_body", ""))
            recipe_id = await conn.fetchval(
                "SELECT id FROM recipe WHERE slug = $1", r.get("slug", "")
            )
            if recipe_id is None:
                continue

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
            parsed_ingredients += sum(1 for i in content.ingredients if i.parsed)
            unparsed_lines += sum(1 for i in content.ingredients if not i.parsed)

            await conn.execute("DELETE FROM recipe_step WHERE recipe_id = $1", recipe_id)
            for step in content.steps:
                await conn.execute(
                    "INSERT INTO recipe_step (recipe_id, position, text) VALUES ($1,$2,$3)",
                    recipe_id, step.position, step.text,
                )
            parsed_steps += len(content.steps)

            if content.ingredients and content.parse_rate < 0.5:
                warnings.append(
                    f"{r.get('slug')}: seulement {content.parse_rate:.0%} des ingrédients "
                    "structurés — vérifier le format de la section"
                )

        # Convives — la table était restée VIDE depuis la création du projet :
        # les profils vivaient dans le vault mais rien ne les ingérait, donc
        # l'app ignorait qui mange quoi. C'est ce qui a laissé passer des wraps
        # au poulet devant une pescétarienne (2026-08-04).
        for convive in convives:
            await conn.execute(
                """INSERT INTO convive (name, constraints, notes)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (name) DO UPDATE SET
                       constraints = $2, notes = $3, ingested_at = NOW()""",
                convive.name,
                [f"diet:{convive.diet}"]
                + [f"avoid:{t}" for t in convive.forbidden]
                + [f"dislike:{t}" for t in convive.dislikes],
                "invité récurrent" if convive.is_guest else "foyer",
            )

        # PAS de DELETE FROM menu : l'upsert par slug suffit désormais à dédoublonner.
        # Le DELETE détruisait tout menu absent du vault — y compris ceux créés via
        # POST /api/menus (incident 2026-08-04 : le menu structuré « Semaine du 3 au 7
        # août » effacé par une ingestion de recettes).
        for m in menus:
            await conn.execute(UPSERT_MENU, *_menu_row(m))

        meals_linked, meals_orphan = await _link_meals(conn)

    return {
        "recipes_ingested": len(recipes),
        "menus_ingested": len(menus),
        "meals_linked": meals_linked,
        "meals_orphan": meals_orphan,
        "convives_ingested": len(convives),
        "photos_linked": photos_linked,
        "ingredients_parsed": parsed_ingredients,
        "ingredients_raw_only": unparsed_lines,
        "steps_parsed": parsed_steps,
        "warnings": warnings,
    }


SLOTS = ("breakfast", "lunch", "snack", "dinner")


async def _link_meals(conn) -> tuple[int, int]:
    """Éclate `menu.meals` (JSONB) en lignes `menu_meal`, recettes résolues.

    C'est ici que le menu cesse d'être un bloc de texte et devient un graphe :
    chaque repas pointe (ou non) une recette. Sans ça, « quelles recettes cette
    semaine ? » n'a pas de réponse, et la liste de courses doit deviner à
    chaque appel.

    ⚠️ Une recette refaite plusieurs fois dans la semaine produit **plusieurs
    lignes** — le dénombrement se fait en aval (`COUNT`), pas en écrasant.

    ⚠️ Un repas non relié reste inséré, `recipe_id = NULL`. Le faire
    disparaître le rendrait invisible partout, y compris dans les manques
    signalés par la liste de courses.
    """
    recipes = await conn.fetch("SELECT id, title FROM recipe")
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

        # Réécriture complète des repas de CE menu : le vault fait autorité sur
        # sa propre semaine. Le CASCADE ne touche aucun autre menu.
        await conn.execute("DELETE FROM menu_meal WHERE menu_id = $1", menu["id"])

        for position, meal in enumerate(meals, start=1):
            for slot in SLOTS:
                dish = (meal.get(slot) or "").strip()
                if not dish:
                    continue
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
    return linked, orphan


def _resolve_dish(dish: str, by_norm: dict) -> tuple[int | None, str | None]:
    """Intitulé de repas → recette, avec le motif d'appariement retenu.

    Les intitulés sont rédigés à la main (« Gratin courgettes-ricotta-feta +
    crevettes sautées citron ») et ne collent jamais au titre de la fiche. On
    reste prudent : mieux vaut ne pas relier — et laisser `recipe_id` à NULL —
    que rattacher la mauvaise recette et acheter ses ingrédients. Le motif est
    stocké pour qu'un appariement approximatif reste contestable.
    """
    norm = normalize_name(dish or "")
    if not norm:
        return None, None
    if norm in by_norm:
        return by_norm[norm]["id"], "exact"
    # L'inclusion joue dans les DEUX SENS, et c'est nécessaire : la fiche est
    # souvent plus détaillée que l'intitulé du menu (« Wraps poulet froid +
    # crudités » au menu, « … + ranch skyr » en fiche). Ne tester qu'un sens
    # laissait ces repas orphelins — donc leurs ingrédients hors des courses.
    for key, recipe in by_norm.items():
        # Seuil de 12 caractères sur la partie COMMUNE : en dessous, un titre
        # court (« Œufs ») s'accrocherait à tout intitulé qui le mentionne.
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


async def run_ingest(vault_root: str, dsn: str) -> dict:
    return await ingest(Path(vault_root), dsn)
