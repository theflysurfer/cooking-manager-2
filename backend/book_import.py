"""Page de livre photographiée → brouillon de recette (lecture vision, structuration maison)."""

from __future__ import annotations

import base64
import json
import logging
import re
import unicodedata
from dataclasses import asdict
from datetime import date

import httpx

from backend.images import ImageGenerationError, api_key
from cooking_manager.ingredients import parse_ingredient
from cooking_manager.normalizer import slugify

logger = logging.getLogger("backend.book_import")

PROMPT_VERSION = "1.0.0"

MODEL = "gemini-3.1-flash-image-preview"
API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
TIMEOUT_S = 120.0

READ_PROMPT = """Tu transcris une page de livre de cuisine photographiée.

Rends UNIQUEMENT un objet JSON, sans texte autour, avec ces clés :

{
  "title": "titre principal, en minuscules accentuées normales",
  "subtitle": "sous-titre ou null",
  "category": "entrée | plat | dessert | apéritif | null (souvent en pied de page)",
  "prep_time_min": entier ou null,
  "cook_time_min": entier ou null,
  "rest_time_min": entier ou null,
  "yield_raw": "la ligne de rendement TELLE QUELLE, ex: POUR 4 PERSONNES",
  "ingredient_groups": [
    {"section": "nom du groupe ou null", "lines": ["300 g de brocciu", "..."]}
  ],
  "steps": ["une entrée par paragraphe d'instruction", "..."]
}

RÈGLES ABSOLUES :
- Recopie chaque ligne d'ingrédient EXACTEMENT comme imprimée : garde la
  quantité, l'unité, les fractions (½, ⅓), les parenthèses, le mot « de ».
- Ne convertis RIEN. Ne traduis RIEN. N'ajoute AUCUN ingrédient absent.
- Ne devine pas une quantité manquante : recopie la ligne sans quantité.
- Les sous-groupes (« Pour la farce », « Pour la sauce ») deviennent `section`.
- Si un champ est illisible, mets null. Ne comble jamais par plausibilité.
- Ignore le numéro de page, mais garde la catégorie du pied de page.
"""

_APPROX_WORDS: dict[str, int] = {
    "demi-douzaine": 6, "douzaine": 12, "dizaine": 10, "quinzaine": 15,
    "vingtaine": 20, "trentaine": 30, "quarantaine": 40, "cinquantaine": 50,
}

_YIELD_RE = re.compile(
    r"pour\s+(?:une\s+|un\s+)?"
    r"(?:(?P<word>[a-zéèêà-]+aine|douzaine)|(?P<num>\d+)(?:\s*[-–—à]\s*(?P<num2>\d+))?)"
    r"\s*(?:de\s+|d')?(?P<unit>[^,(]*)",
    re.IGNORECASE,
)

_PLURAL_EXCEPTIONS = {"foccacine", "pains", "biscuits"}


def _singularize(word: str) -> str:
    """Pluriel français → singulier, pour les seuls cas rencontrés en cuisine."""
    w = word.strip().lower()
    if w.endswith("aux"):
        return w[:-3] + "al"
    if w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def parse_yield(raw: str | None) -> tuple[int | None, str | None]:
    """« POUR 4 PERSONNES » → (4, "personne") ; sur une fourchette, la borne basse."""
    if not raw:
        return None, None
    m = _YIELD_RE.search(raw)
    if not m:
        return None, None

    if m.group("word"):
        qty = _APPROX_WORDS.get(m.group("word").lower())
    else:
        qty = int(m.group("num"))
    unit_raw = (m.group("unit") or "").strip(" .:;")
    unit = _singularize(unit_raw.split()[0]) if unit_raw else None
    return qty, unit or None


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    ).lower()


_CATEGORIES = {"entree": "entrée", "plat": "plat", "dessert": "dessert",
               "aperitif": "apéritif"}


def normalize_category(value: str | None) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return _CATEGORIES.get(_strip_accents(value).strip())


async def read_page(pages: list[tuple[bytes, str]]) -> dict:
    """Photo(s) de page, chacune avec son type MIME → champs bruts. N'écrit rien."""
    key = api_key()
    if not key:
        raise ImageGenerationError(
            "no Gemini API key — expected a Gemini credential "
            "or GEMINI_API_KEY in the environment"
        )
    if not pages:
        raise ValueError("no image supplied")

    parts: list[dict] = [{"text": READ_PROMPT}]
    for raw, mime in pages:
        parts.append(
            {"inlineData": {"mimeType": mime, "data": base64.b64encode(raw).decode()}}
        )

    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        resp = await client.post(
            f"{API_ROOT}/{MODEL}:generateContent",
            params={"key": key},
            json={"contents": [{"parts": parts}],
                  "generationConfig": {"responseMimeType": "application/json"}},
        )
    if resp.status_code != 200:
        raise ImageGenerationError(f"Gemini HTTP {resp.status_code}: {resp.text[:300]}")
    return _extract_json(resp.json())


def _extract_json(data: dict) -> dict:
    """Objet JSON de la réponse ; lève si la réponse 200 ne porte rien de lisible."""
    for candidate in data.get("candidates") or []:
        for part in (candidate.get("content") or {}).get("parts") or []:
            text = part.get("text")
            if not text:
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                stripped = re.sub(r"^```(?:json)?|```$", "", text.strip(),
                                  flags=re.MULTILINE).strip()
                return json.loads(stripped)
    reason = (data.get("promptFeedback") or {}).get("blockReason")
    raise ImageGenerationError(f"no readable page in Gemini response (blockReason={reason})")


def to_draft(page: dict) -> dict:
    """Champs bruts → brouillon structuré, en passant par le parser maison."""
    title = (page.get("title") or "").strip()
    if title:
        title = title[0].upper() + title[1:]
    subtitle = (page.get("subtitle") or "").strip() or None

    ingredients: list[dict] = []
    position = 0
    for group in page.get("ingredient_groups") or []:
        section = (group.get("section") or "").strip() or None
        for line in group.get("lines") or []:
            if not (line or "").strip():
                continue
            position += 1
            ing = asdict(parse_ingredient(line, position))
            ing["section"] = section
            ingredients.append(ing)

    steps = [
        {"position": i, "text": t.strip()}
        for i, t in enumerate(
            [s for s in (page.get("steps") or []) if (s or "").strip()], start=1
        )
    ]

    yield_qty, yield_unit = parse_yield(page.get("yield_raw"))
    servings = yield_qty if yield_unit == "personne" else None

    return {
        "slug": slugify(title) if title else "",
        "title": title,
        "subtitle": subtitle,
        "recipe_type": normalize_category(page.get("category")),
        "prep_time_min": page.get("prep_time_min"),
        "cook_time_min": page.get("cook_time_min"),
        "rest_time_min": page.get("rest_time_min"),
        "yield_raw": page.get("yield_raw"),
        "yield_qty": yield_qty,
        "yield_unit": yield_unit,
        "servings": servings,
        "ingredients": ingredients,
        "steps": steps,
        "unparsed_count": sum(1 for i in ingredients if not i["parsed"]),
        "prompt_version": PROMPT_VERSION,
    }


def _yaml_str(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def to_markdown(draft: dict, source: str | None = None) -> str:
    """Brouillon validé → corps markdown de la recette, relu par `parse_recipe_body`."""
    today = date.today().isoformat()
    fm: list[str] = [
        "---",
        f"title: {_yaml_str(draft['title'])}",
        f"slug: {draft['slug']}",
        "statut: a-tester",
    ]
    if draft.get("recipe_type"):
        fm.append(f"type: {draft['recipe_type']}")
    if draft.get("servings"):
        fm.append(f"portions: {draft['servings']}")
    for key, field in (("temps_preparation", "prep_time_min"),
                       ("temps_cuisson", "cook_time_min")):
        if draft.get(field):
            fm.append(f"{key}: {draft[field]}")
    if source:
        fm += ["sources:", f"  - {_yaml_str(source)}"]
    fm += [f"created: {today}", f"updated: {today}", "---", ""]

    body: list[str] = [f"# {draft['title']}", ""]
    if draft.get("subtitle"):
        body += [f"*{draft['subtitle']}*", ""]

    header = "## Ingrédients"
    if draft.get("yield_raw"):
        header += f" ({draft['yield_raw'].strip().lower()})"
    body += [header, ""]

    current: object = object()
    for ing in draft["ingredients"]:
        if ing.get("section") != current:
            current = ing.get("section")
            if current:
                if body and body[-1].startswith("-"):
                    body.append("")
                body += [f"### {current}", ""]
        body.append(f"- {ing['raw']}")
    body.append("")

    if draft["steps"]:
        body += ["## Préparation", ""]
        body += [f"{s['position']}. {s['text']}" for s in draft["steps"]]
        body.append("")

    return "\n".join(fm + body)
