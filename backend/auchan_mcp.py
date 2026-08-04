"""Auchan Drive MCP server — local replacement for the claude.ai MCP.

Exposes search, product detail, cart operations (including remove).
Run: python -m backend.auchan_mcp
"""

import json
import os
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from .auchan import (
    AuchanClient,
    scrape_product_detail,
    search_products,
)

mcp = FastMCP(
    "Auchan Drive",
    instructions=(
        "Auchan Drive grocery shopping — local API. "
        "Search products, view nutrition/ingredients, manage cart including REMOVE. "
        "Requires a Bearer token from browser session for cart operations."
    ),
)

_client: AuchanClient | None = None


def _get_client() -> AuchanClient:
    global _client
    if _client is None:
        token = os.environ.get("AUCHAN_TOKEN", "")
        cart_id = os.environ.get("AUCHAN_CART_ID")
        _client = AuchanClient(token=token, cart_id=cart_id)
    return _client


@mcp.tool()
async def grocery_search(query: str, page: int = 1) -> str:
    """Search Auchan Drive products. Returns product names, brands, IDs."""
    results = await search_products(query, page)
    return json.dumps(
        [asdict(r) for r in results],
        ensure_ascii=False, indent=2,
    )


@mcp.tool()
async def grocery_product_detail(auchan_id: str) -> str:
    """Get detailed product info: nutrition, ingredients, allergens, nutriscore."""
    url = f"https://www.auchan.fr/p/pr-{auchan_id}"
    detail = await scrape_product_detail(url)
    return json.dumps(asdict(detail), ensure_ascii=False, indent=2)


@mcp.tool()
async def grocery_get_cart() -> str:
    """Get current cart: items, quantities, prices, total."""
    client = _get_client()
    cart = await client.get_cart()
    items = []
    for item in cart.get("items", []):
        offering = item.get("offering", {})
        prices = offering.get("prices", {})
        total_price = prices.get("totalPrice", {})
        unit_price = prices.get("unitPrice", {})
        items.append({
            "id": item["id"],
            "product_id": item["productId"],
            "offer_id": item["offerId"],
            "quantity": item["desiredQuantity"],
            "unit_price": unit_price.get("amount", 0) / 100,
            "total_price": total_price.get("amount", 0) / 100,
        })
    return json.dumps({
        "cart_id": cart["id"],
        "items": items,
        "item_count": len(items),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def grocery_add_to_cart(
    product_id: str, offer_id: str, quantity: int = 1,
) -> str:
    """Add a product to cart."""
    client = _get_client()
    await client.add_to_cart(product_id, offer_id, quantity)
    return json.dumps({"added": product_id, "quantity": quantity}, ensure_ascii=False)


@mcp.tool()
async def grocery_remove_from_cart(product_id: str) -> str:
    """Remove a product from cart by its product ID."""
    client = _get_client()
    result = await client.remove_from_cart(product_id)
    if "error" in result:
        return json.dumps(result, ensure_ascii=False)
    return json.dumps({"removed": product_id}, ensure_ascii=False)


@mcp.tool()
async def grocery_update_quantity(product_id: str, quantity: int) -> str:
    """Update quantity of a product already in cart."""
    client = _get_client()
    result = await client.update_quantity(product_id, quantity)
    if "error" in result:
        return json.dumps(result, ensure_ascii=False)
    return json.dumps(
        {"updated": product_id, "new_quantity": quantity},
        ensure_ascii=False,
    )


@mcp.tool()
async def grocery_persist_cart(
    date: str,
    store: str,
    items_json: str,
    cart_id: str = "",
    covers: int = 0,
    people_csv: str = "",
    total: float = 0.0,
    notes: str = "",
    enrich_nutrition: bool = True,
) -> str:
    """Persist a cart/order to the Cooking Manager database (shopping_session +
    shopping_product), enriching each item with nutrition/nutriscore/ingredients/
    allergens fetched live from the Auchan public catalog.

    items_json: JSON array of objects with keys item_requested, product_name,
    brand, product_id, price_unit, quantity_bought, total_price, rationale
    (rationale required, non-empty).

    Calls the backend's /api/shopping/persist-cart endpoint (COOKING_MANAGER_API_BASE
    env var, defaults to the VPS) — this is the same enrichment pipeline
    (backend/auchan.py::find_product_detail) whichever caller triggers it.
    """
    import httpx as _httpx

    api_base = os.environ.get("COOKING_MANAGER_API_BASE", "https://cooking.srv759970.hstgr.cloud")
    items = json.loads(items_json)
    people = [p.strip() for p in people_csv.split(",") if p.strip()]

    payload = {
        "meta": {
            "date": date, "store": store, "cart_id": cart_id or None,
            "covers": covers or None, "people": people,
            "total": total or None, "items_count": len(items),
            "notes": notes or None,
        },
        "items": items,
        "enrich_nutrition": enrich_nutrition,
    }

    async with _httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(f"{api_base}/api/shopping/persist-cart", json=payload)
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False)


@mcp.tool()
async def grocery_set_token(token: str, cart_id: str = "") -> str:
    """Set the Bearer token and optionally cart ID for cart operations."""
    global _client
    _client = AuchanClient(token=token, cart_id=cart_id or None)
    return json.dumps({"authenticated": True})


if __name__ == "__main__":
    mcp.run(transport="stdio")
