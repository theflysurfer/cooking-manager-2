from __future__ import annotations

import json
import re

from backend.url_parser.ingredients import parse_ingredient
from backend.url_parser.models import Ingredient, Recipe, Step


def _find_recipe_jsonld(html: str) -> dict | None:
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            continue

        recipe = _dig_recipe(data)
        if recipe:
            return recipe
    return None


def _dig_recipe(data: object) -> dict | None:
    if isinstance(data, dict):
        schema_type = data.get("@type", "")
        if isinstance(schema_type, list):
            schema_type = " ".join(schema_type)
        if "Recipe" in schema_type:
            return data
        for v in data.values():
            found = _dig_recipe(v)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _dig_recipe(item)
            if found:
                return found
    return None


def _parse_servings(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d+)", str(text))
    return int(m.group(1)) if m else None


def _parse_duration(raw: str | None) -> str | None:
    if not raw:
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", str(raw), re.IGNORECASE)
    if not m:
        return str(raw)
    parts = []
    if m.group(1):
        parts.append(f"{m.group(1)}h")
    if m.group(2):
        parts.append(f"{m.group(2)}min")
    if m.group(3):
        parts.append(f"{m.group(3)}s")
    return " ".join(parts) if parts else str(raw)


def _extract_steps(instructions: object) -> list[Step]:
    steps: list[Step] = []
    if isinstance(instructions, str):
        for i, line in enumerate(instructions.split("\n"), 1):
            text = line.strip()
            if text:
                steps.append(Step(position=i, text=text))
    elif isinstance(instructions, list):
        pos = 0
        for item in instructions:
            if isinstance(item, str):
                pos += 1
                steps.append(Step(position=pos, text=item.strip()))
            elif isinstance(item, dict):
                if item.get("@type") == "HowToSection":
                    for sub in item.get("itemListElement", []):
                        if isinstance(sub, dict):
                            pos += 1
                            steps.append(Step(position=pos, text=sub.get("text", "").strip()))
                else:
                    pos += 1
                    steps.append(Step(position=pos, text=item.get("text", "").strip()))
    return steps


def _extract_ingredients(raw_list: list) -> list[Ingredient]:
    ingredients: list[Ingredient] = []
    for i, item in enumerate(raw_list, 1):
        text = item if isinstance(item, str) else str(item)
        ingredients.append(parse_ingredient(text, i))
    return ingredients


def _first_text(value) -> str | None:
    """schema.org autorise une liste ou un objet là où le modèle attend une chaîne."""
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get("name") or value.get("@value") or value.get("text")
    if isinstance(value, str):
        return value.strip() or None
    return None


def extract_from_jsonld(html: str, url: str | None = None) -> Recipe | None:
    data = _find_recipe_jsonld(html)
    if not data:
        return None

    raw_ingredients = data.get("recipeIngredient", [])
    if not isinstance(raw_ingredients, list):
        raw_ingredients = [raw_ingredients] if raw_ingredients else []

    image = data.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    elif isinstance(image, dict):
        image = image.get("url")

    return Recipe(
        title=_first_text(data.get("name")),
        description=_first_text(data.get("description")),
        image=str(image) if image else None,
        site_name=None,
        url=url,
        category=_first_text(data.get("recipeCategory")),
        base_servings=_parse_servings(data.get("recipeYield")),
        prep_time=_parse_duration(data.get("prepTime")),
        cook_time=_parse_duration(data.get("cookTime")),
        total_time=_parse_duration(data.get("totalTime")),
        ingredients=_extract_ingredients(raw_ingredients),
        steps=_extract_steps(data.get("recipeInstructions", [])),
        source_tier="jsonld",
    )
