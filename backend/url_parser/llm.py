from __future__ import annotations

import json
import logging
import re

from backend.url_parser.ingredients import parse_ingredient
from backend.url_parser.models import Ingredient, Recipe, Step

logger = logging.getLogger("cooking_manager.url_parser")

_SYSTEM_PROMPT = """Extract recipe data from the provided text. Return ONLY valid JSON with this structure:
{
  "title": "recipe name",
  "description": "short description",
  "base_servings": 4,
  "ingredients": ["200 g flour", "3 eggs", "100 ml milk"],
  "steps": ["Mix dry ingredients.", "Add wet ingredients.", "Bake at 180°C for 30 min."]
}
Return null for missing fields. Ingredients as raw text lines. Steps as plain text."""


def extract_with_llm(
    text: str,
    url: str | None = None,
    *,
    ollama_host: str = "https://ollama.com",
    model: str = "gemma3:cloud",
) -> Recipe | None:
    try:
        import ollama
    except ImportError:
        logger.warning("enable_llm demandé mais le paquet ollama est absent — étage LLM non exécuté")
        return None

    client = ollama.Client(host=ollama_host)
    trimmed = text[:8000]

    try:
        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": trimmed},
            ],
        )
    except Exception as exc:
        logger.warning("étage LLM %s injoignable : %s", model, exc)
        return None

    content = response.get("message", {}).get("content", "")
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if not m:
        return None

    try:
        data = json.loads(m.group())
    except json.JSONDecodeError:
        return None

    raw_ingredients = data.get("ingredients", [])
    if not isinstance(raw_ingredients, list):
        return None

    ingredients: list[Ingredient] = []
    for i, line in enumerate(raw_ingredients, 1):
        if isinstance(line, str) and line.strip():
            ingredients.append(parse_ingredient(line, i))

    raw_steps = data.get("steps", [])
    steps: list[Step] = []
    for i, step in enumerate(raw_steps if isinstance(raw_steps, list) else [], 1):
        if isinstance(step, str) and step.strip():
            steps.append(Step(position=i, text=step.strip()))

    if not ingredients:
        return None

    servings = data.get("base_servings")

    return Recipe(
        title=data.get("title"),
        description=data.get("description"),
        url=url,
        base_servings=int(servings) if servings else None,
        ingredients=ingredients,
        steps=steps,
        source_tier="llm",
    )
