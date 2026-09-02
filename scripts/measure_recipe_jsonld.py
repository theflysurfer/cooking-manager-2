"""Mesure le taux de présence et de complétude du JSON-LD schema.org/Recipe (deep-research#49)."""

import asyncio
import json
import sys
from dataclasses import asdict

sys.path.insert(0, r"E:\Dr2\Dropbox\JULIEN\Coding\_Projets de code\2026.07 Deep Research")

import httpx

from deep_research.lifestyle.recipe_structured import fetch_structured_recipe  # type: ignore[import-not-found]

RECIPES = [
    "https://www.750g.com/bowl-spring-r205366.htm",
    "https://www.750g.com/avocat-saumon-fume-et-lentilles-beluga-sesame-r205275.htm",
    "https://www.750g.com/gratin-de-courgettes-tomates-cerises-et-feta-r71624.htm",
    "https://www.750g.com/gratin-de-pois-chiches-r62923.htm",
    "https://www.750g.com/feta-rotie-aux-pois-chiches-r208774.htm",
    "https://www.750g.com/bouchees-de-courgettes-a-la-feta-r92965.htm",
    "https://www.750g.com/courgettes-grillees-a-la-feta-et-pignons-de-pin-r207620.htm",
    "https://www.750g.com/soupe-de-lentilles-corail-coco-et-curry-r91051.htm",
    "https://www.750g.com/veloute-de-potimarron-aux-lentilles-corail-curry-et-lait-de-coco-r91072.htm",
    "https://www.750g.com/mijote-de-poisson-au-curry-et-lait-de-coco-r90693.htm",
    "https://www.750g.com/salade-de-quinoa-et-lentilles-corail-r99182.htm",
    "https://www.750g.com/salade-de-quinoa-aux-crevettes-sautees-r34366.htm",
    "https://www.750g.com/salade-gourmande-lentilles-crevettes-r202553.htm",
    "https://www.750g.com/salade-de-quinoa-aux-crevettes-marinees-r56424.htm",
    "https://www.750g.com/salade-terre-et-mer-r23616.htm",
    "https://www.750g.com/poulet-en-cocotte-au-vin-blanc-tomates-et-oignons-aux-fines-herbes-r34197.htm",
    "https://www.750g.com/cocotte-de-poulet-mijote-de-ma-grand-mere-r33093.htm",
    "https://www.750g.com/poulet-aux-olives-et-aux-tomates-r100365.htm",
    "https://www.ricardocuisine.com/en/recipes/2048-oat-encrusted-spicy-salmon-on-lime-chickpea-puree",
    "https://www.ricardocuisine.com/en/recipes/4083-balsamic-glazed-salmon-with-lentils",
    "https://www.ricardocuisine.com/en/recipes/10852-hearty-lentil-chickpea-and-vegetable-soup",
    "https://www.ricardocuisine.com/en/recipes/6035-coconut-fish-curry",
    "https://www.ricardocuisine.com/en/recipes/466-quinoa-and-shrimp-salad",
    "https://www.papillesetpupilles.fr/2026/05/dahl-ultra-cremeux-aux-lentilles-corail.html/",
    "https://www.papillesetpupilles.fr/2018/10/lentilles-aux-epices-et-au-lait-de-coco-dahl.html/",
    "https://www.papillesetpupilles.fr/2020/11/dahl-de-lentilles-corail-au-poulet-et-au-curry.html/",
    "https://www.papillesetpupilles.fr/2026/07/courgettes-aux-pois-chiches-tomate-citron-et-basilic.html/",
    "https://www.papillesetpupilles.fr/2013/06/salade-de-quinoa-a-la-feta-et-a-la-grenade.html/",
    "https://www.papillesetpupilles.fr/2020/07/salade-de-quinoa-crevettes-et-menthe.html/",
    "https://www.papillesetpupilles.fr/2012/01/salade-de-lentilles-aux-patates-douces-grillees-et-a-la-feta.html/",
    "https://www.papillesetpupilles.fr/2018/08/poulet-aux-tomates-et-aux-champignons.html/",
    "https://www.papillesetpupilles.fr/2017/03/poulet-aux-carottes-pommes-de-terre-et-epices-douces.html/",
    "https://www.hervecuisine.com/recette/recette-du-poke-bol-saumon/",
    "https://www.hervecuisine.com/recette/la-recette-du-curry-de-lentilles-corail-ou-dhal/",
]

CONTROLS = [
    "https://www.750g.com/recettes-salades/composees/lentilles/",
    "https://www.papillesetpupilles.fr/recettes/plats-mijotes/",
]


async def one(url: str, client: httpx.AsyncClient, gate: asyncio.Semaphore) -> dict:
    async with gate:
        try:
            result = await asyncio.wait_for(fetch_structured_recipe(url, client), timeout=60)
        except Exception as exc:
            return {"url": url, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    row = {"url": url, "ok": result.ok, "error": result.error}
    if result.recipe is not None:
        r = result.recipe
        row.update(
            {
                "title": r.title,
                "method": r.method,
                "servings": r.servings,
                "n_ingredients": len(r.ingredients),
                "n_steps": len(r.steps),
                "total_time_minutes": r.total_time_minutes,
                "has_nutrition": bool(r.nutrition),
                "nutrition_keys": sorted(r.nutrition),
                "ingredients": [asdict(i) for i in r.ingredients],
                "steps": r.steps,
            }
        )
    return row


async def main() -> None:
    gate = asyncio.Semaphore(6)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        rows = await asyncio.gather(
            *(one(u, client, gate) for u in RECIPES + CONTROLS)
        )
    out = {"recipes": rows[: len(RECIPES)], "controls": rows[len(RECIPES) :]}
    with open("jsonld_measure.json", "w", encoding="utf-8") as handle:
        json.dump(out, handle, ensure_ascii=False, indent=1)
    ok = sum(1 for r in out["recipes"] if r["ok"])
    print(f"recettes: {ok}/{len(RECIPES)} extraites")
    print(f"controles (doivent echouer): {sum(1 for r in out['controls'] if r['ok'])}/{len(CONTROLS)} extraits")


asyncio.run(main())
