"""Multi-store product search — Auchan + Leclerc behind a common interface.

Search is auth-free for both stores (Auchan uses hardcoded store cookies,
Leclerc cookies are loaded from credstore/env/Hydra profile).
Cart operations need per-store auth tokens — wired but require setup.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, asdict

log = logging.getLogger(__name__)

SUPPORTED_STORES = ("auchan", "leclerc")


@dataclass
class StoreProduct:
    product_id: str
    name: str
    brand: str
    image_url: str
    price: float | None
    price_per_unit: str
    nutriscore: str
    store: str
    offer_id: str = ""


async def search_store(store: str, query: str, limit: int = 5) -> list[StoreProduct]:
    if store == "auchan":
        return await _search_auchan(query, limit)
    if store == "leclerc":
        return await _search_leclerc(query, limit)
    raise ValueError(f"Enseigne inconnue : {store}")


async def map_ingredients(
    store: str,
    ingredients: list[dict],
    concurrency: int = 3,
) -> list[dict]:
    """Batch: search best product match for each ingredient, in parallel."""
    sem = asyncio.Semaphore(concurrency)

    async def _one(ing: dict) -> dict:
        query = ing.get("name_normalized") or ing["name"]
        async with sem:
            try:
                results = await search_store(store, query)
            except Exception as exc:
                log.warning("search failed for %r on %s: %s", query, store, exc)
                results = []
        return {
            "ingredient": ing["name"],
            "qty": ing.get("qty"),
            "unit": ing.get("unit"),
            "recipes": ing.get("recipes", []),
            "results": [asdict(p) for p in results],
            "selected": 0 if results else -1,
        }

    return list(await asyncio.gather(*[_one(i) for i in ingredients]))


# ── Auchan ────────────────────────────────────────────────────────────

async def _search_auchan(query: str, limit: int = 5) -> list[StoreProduct]:
    from .auchan import search_products

    results = await search_products(query)
    out: list[StoreProduct] = []
    for r in results[:limit]:
        price = _parse_price(r.price) if r.price else None
        out.append(StoreProduct(
            product_id=r.auchan_id,
            name=r.name,
            brand=r.brand,
            image_url=r.image_url,
            price=price,
            price_per_unit="",
            nutriscore="",
            store="auchan",
        ))
    return out


# ── Leclerc ───────────────────────────────────────────────────────────

async def _search_leclerc(query: str, limit: int = 5) -> list[StoreProduct]:
    try:
        from leclerc_drive.client import _parse_search_results  # type: ignore[import-untyped]
        from leclerc_drive.cookies import load_leclerc_cookies  # type: ignore[import-untyped]
    except ImportError:
        log.warning("leclerc_drive not installed — Leclerc search unavailable")
        return []

    cookie_str = load_leclerc_cookies()
    if not cookie_str:
        log.warning("No Leclerc cookies found")
        return []

    cookies = dict(
        part.split("=", 1)
        for part in cookie_str.split("; ")
        if "=" in part
    )
    url = (
        "https://fd4-courses.leclercdrive.fr/"
        "magasin-997371-000011-Paris/recherche.aspx"
        f"?TexteRecherche={query}"
    )

    from .stealth import fetch_html
    try:
        html = await fetch_html(url, cookies=cookies, max_level=5)
    except Exception as exc:
        log.warning("Leclerc search error for %r: %s", query, exc)
        return []

    results = _parse_search_results(html)
    return [
        StoreProduct(
            product_id=str(r.product_id),
            name=r.name,
            brand="",
            image_url=getattr(r, "image_url", "") or "",
            price=r.price,
            price_per_unit=getattr(r, "price_per_unit", "") or "",
            nutriscore=getattr(r, "nutriscore", "") or "",
            store="leclerc",
        )
        for r in results[:limit]
    ]


# ── Helpers ───────────────────────────────────────────────────────────

def _parse_price(raw: str) -> float | None:
    try:
        return float(
            raw.replace("\xa0", "").replace("€", "")
            .replace(",", ".").strip()
        )
    except (ValueError, AttributeError):
        return None
