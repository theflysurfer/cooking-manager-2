"""Moissonne des dîners de semaine depuis des pages recette en JSON-LD (schema.org/Recipe).

Le répertoire du foyer n'a que des plats construits : mesuré le 2026-09-20, ses
37 recettes « rapides » sont des assiettes froides de midi. Ce script comble ce
trou, et ne garde que ce que `cooking_manager.effort` juge tenable un soir de
semaine — le filtre est le nôtre, pas la promesse du site.

    python scripts/scrape_weeknight.py --target 50 --out data/scraped_weeknight.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cooking_manager.effort import fits_weeknight, read_effort  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CookingManager/1.0"}
LD = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S)
LINK = re.compile(r'/recettes/recette[_-][a-z0-9\-_]+\.aspx')
BASE = "https://www.marmiton.org"

INDEX = "/recettes/index/categorie/{cat}/{page}"
CATEGORIES = ("plat-principal", "accompagnement")
PAGES = range(1, 26)

FAMILY_CAP = 3
"""Sans plafond, un BFS reste dans son voisinage : la première moisson a rendu
20 gratins de macaronis sur 50 (mesuré le 2026-09-20)."""

DESSERT = re.compile(
    r"gateau|tarte au (?:citron|chocolat)|brownie|cookie|pavlova|crumble|mousse au chocolat"
    r"|cr[eè]me br[uû]l[eé]e|muffin|madeleine|sorbet|glace|confiture|p[aâ]te [aà] cr[eê]pes"
    r"|clafoutis|tiramisu|cheesecake|verrine sucr", re.I
)

def _iso_minutes(value: str | None) -> int | None:
    """« PT1H30M » → 90. Une durée absente reste None, jamais zéro."""
    if not value:
        return None
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?", str(value).strip())
    if not m or not any(m.groups()):
        return None
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)

def _steps(raw) -> list[str]:
    out: list[str] = []
    for item in raw or []:
        if isinstance(item, dict):
            text = item.get("text") or item.get("name") or ""
        else:
            text = str(item)
        text = re.sub(r"\s+", " ", str(text)).strip()
        if text:
            out.append(text)
    return out

def _yield(raw) -> int | None:
    match = re.search(r"\d+", str(raw or ""))
    return int(match.group(0)) if match else None

def fetch(url: str, timeout: int = 20) -> str | None:
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=timeout
        ) as response:
            return response.read().decode("utf-8", "ignore")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None

def parse_recipe(html: str) -> dict | None:
    for block in LD.findall(html):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        candidates = data.get("@graph") if isinstance(data, dict) else data
        if isinstance(data, dict) and "@graph" not in data:
            candidates = [data]
        for item in candidates or []:
            if not isinstance(item, dict) or "Recipe" not in str(item.get("@type", "")):
                continue
            total = _iso_minutes(item.get("totalTime"))
            if total is None:
                cook = _iso_minutes(item.get("cookTime")) or 0
                prep = _iso_minutes(item.get("prepTime")) or 0
                total = (cook + prep) or None
            category = item.get("recipeCategory")
            if isinstance(category, list):
                category = ", ".join(str(c) for c in category)
            return {
                "title": re.sub(r"\s+", " ", str(item.get("name") or "")).strip(),
                "category": str(category or ""),
                "total_time_min": total,
                "servings": _yield(item.get("recipeYield")),
                "ingredients": [
                    re.sub(r"\s+", " ", str(i)).strip()
                    for i in (item.get("recipeIngredient") or [])
                ],
                "steps": _steps(item.get("recipeInstructions")),
            }
    return None

def family_of(title: str) -> str:
    """La famille d'un plat, pour ne pas moissonner vingt fois le même."""
    words = [w for w in re.split(r"[^a-zA-Zàâäéèêëîïôöùûüç]+", title.lower()) if len(w) > 3]
    skip = {"meilleure", "recette", "facile", "rapide", "maison", "express",
            "grand", "mere", "super", "petits", "petit", "bonne", "delicieux"}
    for word in words:
        if word not in skip:
            return word
    return title.lower()[:8]

def keep(recipe: dict) -> tuple[bool, str]:
    """Notre propre jugement, jamais la promesse du site."""
    if not recipe["title"] or DESSERT.search(recipe["title"]):
        return False, "dessert ou sans titre"
    if "plat principal" not in recipe.get("category", "").lower():
        return False, f"pas un plat principal ({recipe.get('category') or 'sans categorie'})"
    if not recipe["steps"] or not recipe["ingredients"]:
        return False, "fiche incomplète"
    reading = read_effort(recipe["steps"])
    verdict = fits_weeknight(reading, recipe["total_time_min"])
    if verdict is not True:
        return False, f"{reading.band}/{recipe['total_time_min']} min → {verdict}"
    recipe["band"] = reading.band
    recipe["markers"] = list(reading.markers)
    return True, reading.band

def crawl(target: int, budget_s: float, seen: set[str], kept: list[dict]) -> None:
    families: dict[str, int] = {}
    for recipe in kept:
        family = family_of(recipe["title"])
        families[family] = families.get(family, 0) + 1

    started = time.time()
    for page in PAGES:
        for category in CATEGORIES:
            if len(kept) >= target or time.time() - started > budget_s:
                return
            index_url = BASE + INDEX.format(cat=category, page=page)
            index_html = fetch(index_url)
            if not index_html:
                continue
            for path in dict.fromkeys(LINK.findall(index_html)):
                url = BASE + path
                if url in seen or len(kept) >= target:
                    continue
                if time.time() - started > budget_s:
                    return
                seen.add(url)
                html = fetch(url)
                if not html:
                    continue
                recipe = parse_recipe(html)
                if not recipe:
                    continue
                family = family_of(recipe["title"])
                if families.get(family, 0) >= FAMILY_CAP:
                    print(f"  saute   {recipe['title'][:48]:50} famille « {family} » pleine",
                          flush=True)
                    continue
                ok, why = keep(recipe)
                print(("  GARDE  " if ok else "  rejet  ")
                      + f"{recipe['title'][:50]:52} {why}", flush=True)
                if ok:
                    recipe["source"] = url
                    kept.append(recipe)
                    families[family] = families.get(family, 0) + 1
                time.sleep(0.3)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=50)
    parser.add_argument("--budget", type=float, default=150.0)
    parser.add_argument("--out", default="data/scraped_weeknight.json")
    args = parser.parse_args()

    out = Path(args.out)
    state = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    kept: list[dict] = state.get("recipes", [])
    seen: set[str] = set(state.get("seen", []))

    crawl(args.target, args.budget, seen, kept)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"recipes": kept, "seen": sorted(seen)}, ensure_ascii=False, indent=2
    ) + "\n", encoding="utf-8")
    print(f"\n{len(kept)} recettes gardées, {len(seen)} pages vues → {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
