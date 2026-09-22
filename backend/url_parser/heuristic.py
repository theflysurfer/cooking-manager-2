from __future__ import annotations

import re
from selectolax.parser import HTMLParser

from backend.url_parser.ingredients import parse_ingredient
from backend.url_parser.models import Ingredient, Recipe, Step

_INGREDIENT_SELECTORS = [
    ".recipe-ingredients li",
    ".ingredients li",
    "[class*='ingredient'] li",
    ".recipe__ingredients li",
    ".wprm-recipe-ingredient",
    ".tasty-recipe-ingredients li",
    ".recipe-ingred_txt",
    ".structured-ingredients__list-item",
    "ul.ingredients li",
]

_STEP_SELECTORS = [
    ".recipe-steps li",
    ".recipe-preparation li",
    ".steps li",
    "[class*='instruction'] li",
    ".recipe__steps li",
    ".wprm-recipe-instruction",
    ".tasty-recipe-instructions li",
    ".recipe-directions__list li",
    ".structured-instructions__list-item",
    "ol.preparation li",
    "ol.directions li",
]

_TITLE_SELECTORS = [
    "h1.recipe-title",
    "h1[class*='recipe']",
    ".recipe__title",
    ".wprm-recipe-name",
    ".tasty-recipe-title",
    "h1",
]

_SERVINGS_RE = re.compile(
    r"(\d+)\s*(?:portions?|servings?|personnes?|parts?|pers\.?|couverts?)",
    re.IGNORECASE,
)


def _text(node) -> str:
    return node.text(strip=True) if node else ""


def _first_match(tree: HTMLParser, selectors: list[str]):
    for sel in selectors:
        nodes = tree.css(sel)
        if nodes:
            return nodes
    return []


def extract_from_html(html: str, url: str | None = None) -> Recipe | None:
    tree = HTMLParser(html)

    ingredient_nodes = _first_match(tree, _INGREDIENT_SELECTORS)
    step_nodes = _first_match(tree, _STEP_SELECTORS)

    if not ingredient_nodes:
        return None

    ingredients: list[Ingredient] = []
    for i, node in enumerate(ingredient_nodes, 1):
        text = _text(node)
        if text:
            ingredients.append(parse_ingredient(text, i))

    steps: list[Step] = []
    for i, node in enumerate(step_nodes, 1):
        text = _text(node)
        if text:
            steps.append(Step(position=i, text=text))

    title = None
    for sel in _TITLE_SELECTORS:
        node = tree.css_first(sel)
        if node:
            title = _text(node)
            break

    description = None
    meta_desc = tree.css_first('meta[name="description"]')
    if meta_desc:
        description = meta_desc.attributes.get("content")

    image = None
    og_image = tree.css_first('meta[property="og:image"]')
    if og_image:
        image = og_image.attributes.get("content")

    site_name = None
    og_site = tree.css_first('meta[property="og:site_name"]')
    if og_site:
        site_name = og_site.attributes.get("content")

    base_servings = None
    body_text = tree.body.text() if tree.body else ""
    m = _SERVINGS_RE.search(body_text[:5000])
    if m:
        base_servings = int(m.group(1))

    return Recipe(
        title=title,
        description=description,
        image=image,
        site_name=site_name,
        url=url,
        base_servings=base_servings,
        ingredients=ingredients,
        steps=steps,
        source_tier="heuristic",
    )
