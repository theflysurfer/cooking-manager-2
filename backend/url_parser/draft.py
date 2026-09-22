"""Une recette extraite d'une URL → brouillon révisable, même schéma que le livre."""

from __future__ import annotations

import re
from dataclasses import asdict

from backend.book_import import normalize_category
from backend.url_parser.ingredients import normalize_name
from cooking_manager.normalizer import slugify
from backend.url_parser.models import Recipe

DRAFT_SOURCE_VERSION = "url-v1"

_DURATION = re.compile(r"(?:(\d+)\s*h)?\s*(?:(\d+)\s*min)?", re.IGNORECASE)


def duration_minutes(raw: str | None) -> int | None:
    """« 2h 30min » → 150. Rend None plutôt que 0 quand rien n'est lisible."""
    if not raw:
        return None
    match = _DURATION.search(raw.strip())
    if match is None:
        return None
    hours, minutes = match.group(1), match.group(2)
    if hours is None and minutes is None:
        return None
    return int(hours or 0) * 60 + int(minutes or 0)


def is_usable(recipe: Recipe) -> bool:
    """Étapes ET quantités — jamais « le parseur a répondu » (docs/CORPUS_WEB.md)."""
    return bool(recipe.steps) and any(i.quantity is not None for i in recipe.ingredients)


def to_draft(recipe: Recipe) -> dict:
    """Recette extraite → brouillon, sans rien inventer de ce que la source tait."""
    title = (recipe.title or "").strip()
    ingredients = []
    for ingredient in recipe.ingredients:
        row = asdict(ingredient)
        row["qty_min"] = row.pop("quantity")
        row["qty_max"] = row.pop("quantity_max")
        row["name_normalized"] = normalize_name(row["name"])
        row["section"] = None
        ingredients.append(row)

    servings = recipe.base_servings
    return {
        "slug": slugify(title) if title else "",
        "title": title,
        "subtitle": None,
        "recipe_type": normalize_category(recipe.category),
        "prep_time_min": duration_minutes(recipe.prep_time),
        "cook_time_min": duration_minutes(recipe.cook_time),
        "rest_time_min": None,
        "yield_raw": f"{servings} personnes" if servings else None,
        "yield_qty": servings,
        "yield_unit": "personne" if servings else None,
        "servings": servings,
        "ingredients": ingredients,
        "steps": [asdict(step) for step in recipe.steps],
        "unparsed_count": sum(1 for i in ingredients if not i["parsed"]),
        "prompt_version": DRAFT_SOURCE_VERSION,
        "source_url": recipe.url,
        "source_tier": recipe.source_tier,
        "source_category": recipe.category,
        "photo_url": recipe.image,
        "usable": is_usable(recipe),
    }
