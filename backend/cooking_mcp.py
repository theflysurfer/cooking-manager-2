"""Cooking Manager MCP server — pantry + cooking tools for LLMs.

Exposes the pantry (DB-backed), shopping list differential, and recipe search.
Run: python -m backend.cooking_mcp
"""

import json
import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "Cooking Manager",
    instructions=(
        "Garde-manger, liste de courses, et recettes du foyer. "
        "Le garde-manger est la source de vérité pour ce qu'on a en stock. "
        "La liste de courses différentielle croise le menu de la semaine "
        "avec le stock réel."
    ),
)

API_BASE = os.environ.get(
    "COOKING_MANAGER_API_BASE", "https://cooking.srv759970.hstgr.cloud"
)


async def _api(method: str, path: str, body: dict | None = None) -> dict:
    import httpx

    async with httpx.AsyncClient(timeout=30.0) as client:
        if method == "GET":
            r = await client.get(f"{API_BASE}{path}")
        elif method == "POST":
            r = await client.post(f"{API_BASE}{path}", json=body)
        elif method == "PUT":
            r = await client.put(f"{API_BASE}{path}", json=body)
        elif method == "DELETE":
            r = await client.delete(f"{API_BASE}{path}")
        else:
            raise ValueError(f"Unknown method: {method}")
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def pantry_list(section: str = "") -> str:
    """List all pantry items, optionally filtered by section (rayon).

    Returns items grouped by section with status, quantity, and source.
    """
    data = await _api("GET", "/api/pantry")
    if section:
        data["rayons"] = [
            r for r in data["rayons"]
            if section.lower() in r["name"].lower()
        ]
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def pantry_search(query: str) -> str:
    """Search pantry items by name (partial match, case insensitive)."""
    data = await _api("GET", f"/api/pantry/search?q={query}")
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def pantry_add(
    name: str,
    section: str,
    qty_text: str = "",
    status: str = "ok",
    notes: str = "",
) -> str:
    """Add a new item to the pantry.

    section: rayon name, e.g. "Frais — Protéines", "Sec", "Épices"
    status: ok, low, out
    """
    data = await _api("POST", "/api/pantry/items", {
        "name": name,
        "section": section,
        "qty_text": qty_text,
        "status": status,
        "notes": notes or None,
        "source": "voice",
    })
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def pantry_update(
    item_id: int,
    qty_text: str = "",
    status: str = "",
    notes: str = "",
) -> str:
    """Update a pantry item's quantity, status, or notes.

    item_id: from pantry_list or pantry_search results
    status: ok, low, out (or extended: urgent, a-jeter, verifier-dlc)
    """
    body: dict = {}
    if qty_text:
        body["qty_text"] = qty_text
    if status:
        body["status"] = status
    if notes:
        body["notes"] = notes
    data = await _api("PUT", f"/api/pantry/items/{item_id}", body)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def pantry_remove(item_id: int) -> str:
    """Remove an item from the pantry by its ID."""
    data = await _api("DELETE", f"/api/pantry/items/{item_id}")
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def shopping_list(menu_slug: str, covers: int = 4) -> str:
    """Differential shopping list for a menu: crosses recipe needs against pantry.

    Each line has an outcome: suffisant, insuffisant, absent, or inconnu.
    Lines marked 'inconnu' need human confirmation.
    """
    data = await _api(
        "GET", f"/api/menus/{menu_slug}/shopping-list?covers={covers}"
    )
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def recipe_search(query: str = "", family: str = "", tag: str = "") -> str:
    """Search recipes by name, family, or tag."""
    params = []
    if query:
        params.append(f"q={query}")
    if family:
        params.append(f"family={family}")
    if tag:
        params.append(f"tag={tag}")
    qs = "&".join(params) if params else ""
    data = await _api("GET", f"/api/recipes?{qs}&limit=20")
    recipes = [
        {
            "slug": r["slug"],
            "title": r["title"],
            "family": r.get("family"),
            "servings": r.get("servings"),
            "total_time_min": r.get("total_time_min"),
            "macros": r.get("macros"),
            "tags": r.get("tags", []),
        }
        for r in data.get("recipes", [])
    ]
    return json.dumps(
        {"total": data["total"], "recipes": recipes},
        ensure_ascii=False, indent=2,
    )


@mcp.tool()
async def recipe_detail(slug: str) -> str:
    """Get full recipe detail: ingredients, steps, macros."""
    data = await _api("GET", f"/api/recipes/{slug}")
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def menu_current() -> str:
    """Get the most recent menu (current week)."""
    data = await _api("GET", "/api/menus")
    menus = data.get("menus", [])
    if not menus:
        return json.dumps({"error": "Aucun menu trouvé"}, ensure_ascii=False)
    return json.dumps(menus[0], ensure_ascii=False, indent=2)


@mcp.tool()
async def pantry_ingest() -> str:
    """Re-ingest the vault (recipes, menus, pantry) into the database.

    Call after editing Markdown files in Obsidian.
    """
    data = await _api("POST", "/api/ingest")
    return json.dumps(data, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
