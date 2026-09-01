"""Serveur MCP Cooking Manager — garde-manger, courses, recettes et tablée."""

import json
import os

from fastmcp import FastMCP

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
    "COOKING_MANAGER_API_BASE", "http://127.0.0.1:8795"
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
    source: str = "coach",
) -> str:
    """Add a new item to the pantry.

    section: rayon name, e.g. "Frais — Protéines", "Sec", "Épices"
    status: ok, low, out
    source: who observed it — coach, voice, manual, receipt. Anything but
    'vault' makes the row DB-owned, so vault ingestion can never revert it.
    """
    data = await _api("POST", "/api/pantry/items", {
        "name": name,
        "section": section,
        "qty_text": qty_text,
        "status": status,
        "notes": notes or None,
        "source": source,
    })
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def pantry_update(
    item_id: int,
    qty_text: str = "",
    status: str = "",
    notes: str = "",
    source: str = "coach",
) -> str:
    """Update a pantry item's quantity, status, or notes.

    item_id: from pantry_list or pantry_search results
    status: ok, low, out (or extended: urgent, a-jeter, verifier-dlc)
    source: who observed it. The row becomes DB-owned, so the next vault
    ingestion cannot silently revert this update.
    """
    body: dict = {"source": source}
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


@mcp.tool()
async def people_list(circle: str = "") -> str:
    """List people who can be at the table (household, family, friends, guests).

    circle: filter by 'household', 'extended_family', 'friend', 'occasional'.
    Each person carries diet, dislikes, forbidden foods — used by compatibility.
    """
    path = "/api/persons"
    if circle:
        path += f"?circle={circle}"
    data = await _api("GET", path)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def person_add(
    name: str,
    circle: str = "occasional",
    role: str = "adult",
    diet: str = "omnivore",
    dislikes: str = "",
    forbidden: str = "",
) -> str:
    """Add a person (guest, family member) to the roster.

    circle: household | extended_family | friend | occasional
    role: adult | child | caregiver
    diet: omnivore | pescetarian | vegetarian | vegan | semi-vegetarian
    dislikes / forbidden: comma-separated food terms (e.g. "maïs, céleri").
    """
    body = {
        "name": name, "circle": circle, "role": role, "diet": diet,
        "dislikes": [t.strip() for t in dislikes.split(",") if t.strip()],
        "forbidden": [t.strip() for t in forbidden.split(",") if t.strip()],
    }
    data = await _api("POST", "/api/persons", body)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def whos_eating(day: str, slot: str = "") -> str:
    """Who eats on a given day — resolves the table from the DB.

    day: YYYY-MM-DD. slot: breakfast|lunch|snack|dinner (empty = all slots).
    Resolution order: manual override > stay (holiday) > custody/canteen frame
    > absences. Returns the school-holiday label and any covering stay too.
    """
    path = f"/api/attendance?day={day}"
    if slot:
        path += f"&slot={slot}"
    data = await _api("GET", path)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def menu_compatibility(menu_slug: str) -> str:
    """Dietary-compatibility check of a menu, meal by meal.

    Crosses who is actually at each meal (custody, holidays, absences, stays)
    with what each person cannot eat (diet, dislikes, forbidden). Flags every
    conflict. All data comes from the DB — no Markdown.
    """
    data = await _api("GET", f"/api/menus/{menu_slug}/compatibility")
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def stays_list() -> str:
    """List holiday stays (periods away from home where the table changes).

    A stay with cooking=true means the listed members eat every meal there —
    this is what keeps a holiday week from showing an empty table.
    """
    data = await _api("GET", "/api/stays")
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def stay_add(
    label: str,
    start_date: str,
    end_date: str,
    member_ids: str,
    location: str = "",
    cooking: bool = True,
) -> str:
    """Declare a holiday stay — fixes the "empty table on holidays" case (F.30).

    start_date/end_date: YYYY-MM-DD. member_ids: comma-separated person IDs
    (from people_list). cooking=true: we cook on site; false: hotel/no cooking.
    Its members are at the table for every meal of the period, overriding the
    custody/canteen frame and any absences.
    """
    body = {
        "label": label, "start_date": start_date, "end_date": end_date,
        "location": location or None, "cooking": cooking,
        "member_ids": [int(x) for x in member_ids.split(",") if x.strip()],
    }
    data = await _api("POST", "/api/stays", body)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def absence_add(
    person_id: int,
    start_date: str,
    end_date: str,
    slot: str = "",
    reason: str = "",
) -> str:
    """Declare that a person is away — removes them from the table.

    start_date/end_date: YYYY-MM-DD. slot empty = whole day(s); or a single
    slot (breakfast|lunch|snack|dinner) for "eats at the office this lunch".
    """
    body = {
        "person_id": person_id, "start_date": start_date, "end_date": end_date,
        "slot": slot or None, "reason": reason or None,
    }
    data = await _api("POST", "/api/absences", body)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def household_seed() -> str:
    """Seed/refresh the household roster and schedules in the DB (idempotent).

    Populates the resident people, custody and canteen schedules, school
    holidays, and known stays. Safe to re-run.
    """
    data = await _api("POST", "/api/seed")
    return json.dumps(data, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", default="stdio")
    parser.add_argument("--http", type=int, help="HTTP port (implies streamable-http)")
    parser.add_argument("--public-url", help="Public URL for OAuth redirects")
    args = parser.parse_args()

    if args.http:
        import sys

        sys.path.insert(0, "/home/automation/shared")
        from mcp_auth import build_google_auth  # type: ignore[import-not-found]

        public_url = args.public_url or f"http://127.0.0.1:{args.http}"
        mcp.auth = build_google_auth("cooking", server_base_url=public_url)  # type: ignore[assignment]
        mcp.run(
            transport="streamable-http",
            host="127.0.0.1",
            port=args.http,
            allowed_hosts=["cooking-mcp.srv759970.hstgr.cloud"],
        )
    else:
        mcp.run(transport=args.transport)  # type: ignore[arg-type]
