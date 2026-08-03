"""FastAPI application — recipe browser + ingest trigger."""

import json
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import DATABASE_DSN, VAULT_ROOT
from .db import get_pool, init_schema, close_pool
from .ingest import ingest


async def _get_recipe_id(conn, slug: str) -> int:
    row = await conn.fetchrow("SELECT id FROM recipe WHERE slug = $1", slug)
    if not row:
        raise HTTPException(404, "Recipe not found")
    return row["id"]


def _serialize_dates(d: dict, keys: tuple[str, ...]) -> None:
    for key in keys:
        if d.get(key) and hasattr(d[key], "isoformat"):
            d[key] = d[key].isoformat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_schema(DATABASE_DSN)
    yield
    await close_pool()


app = FastAPI(title="Cooking Manager", version="2.0.0", lifespan=lifespan)


# ── API routes ──────────────────────────────────────────────────────

@app.get("/api/recipes")
async def list_recipes(
    status: str | None = None,
    family: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    pool = await get_pool(DATABASE_DSN)
    clauses = []
    params = []
    idx = 1

    if status:
        clauses.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if family:
        clauses.append(f"family = ${idx}")
        params.append(family)
        idx += 1
    if tag:
        clauses.append(f"${idx} = ANY(tags)")
        params.append(tag)
        idx += 1
    if q:
        clauses.append(f"(title ILIKE ${idx} OR slug ILIKE ${idx})")
        params.append(f"%{q}%")
        idx += 1

    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    params.extend([limit, offset])

    sql = f"""
        SELECT id, slug, title, status, recipe_type, family, servings,
               total_time_min, prep_time_min, cook_time_min,
               tags, compatible_constraints, sources, appreciated_by,
               applied_substitutions, mediterranean_criteria,
               construction_regime, execution_count, lieu_execution,
               macros_kcal, macros_protein, macros_carbs, macros_fat,
               protein_density, photo_url, created, updated
        FROM recipe {where}
        ORDER BY title
        LIMIT ${idx} OFFSET ${idx + 1}
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
        total = await conn.fetchval(f"SELECT COUNT(*) FROM recipe {where}", *params[:-2])

    return {
        "total": total,
        "recipes": [_recipe_to_dict(r) for r in rows],
    }


@app.get("/api/recipes/{slug}")
async def get_recipe(slug: str):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM recipe WHERE slug = $1", slug
        )
    if not row:
        raise HTTPException(404, "Recipe not found")
    return _recipe_to_dict(row)


@app.get("/api/filters")
async def get_filters():
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        statuses = await conn.fetch(
            "SELECT DISTINCT status FROM recipe ORDER BY status"
        )
        families = await conn.fetch(
            "SELECT DISTINCT family FROM recipe WHERE family IS NOT NULL ORDER BY family"
        )
        tags = await conn.fetchval("""
            SELECT ARRAY_AGG(DISTINCT t ORDER BY t)
            FROM recipe, UNNEST(tags) AS t
        """)
    return {
        "statuses": [r["status"] for r in statuses],
        "families": [r["family"] for r in families],
        "tags": tags or [],
    }


@app.get("/api/menus")
async def list_menus():
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM menu ORDER BY week_start DESC")
    menus = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("meals"), str):
            d["meals"] = json.loads(d["meals"])
        _serialize_dates(d, ("created", "updated", "week_start", "week_end"))
        menus.append(d)
    return {"menus": menus}


class MenuCreate(BaseModel):
    title: str
    week_start: date | None = None
    week_end: date | None = None
    configuration: str | None = None
    status: str = "proposed"
    linked_recipes: list[str] = []
    meals: list[dict] | None = None
    body: str | None = None


@app.post("/api/menus")
async def create_menu(menu: MenuCreate):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO menu (title, week_start, week_end, configuration, status,
                                linked_recipes, meals, body, created, updated)
               VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, CURRENT_DATE, CURRENT_DATE)
               RETURNING id, title""",
            menu.title, menu.week_start, menu.week_end, menu.configuration,
            menu.status, menu.linked_recipes,
            json.dumps(menu.meals) if menu.meals else None,
            menu.body,
        )
    return {"id": row["id"], "title": row["title"], "created": True}


@app.post("/api/ingest")
async def trigger_ingest():
    result = await ingest(Path(VAULT_ROOT), DATABASE_DSN)
    return result


@app.get("/api/stats")
async def stats():
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM recipe")
        by_status = await conn.fetch(
            "SELECT status, COUNT(*) as count FROM recipe GROUP BY status ORDER BY status"
        )
        by_family = await conn.fetch(
            "SELECT family, COUNT(*) as count FROM recipe WHERE family IS NOT NULL GROUP BY family ORDER BY count DESC"
        )
    return {
        "total_recipes": total,
        "by_status": {r["status"]: r["count"] for r in by_status},
        "by_family": {r["family"]: r["count"] for r in by_family},
    }


class ExecutionCreate(BaseModel):
    date: date
    cooked_by: str | None = None
    rating: int | None = None
    appreciated_by: list[str] = []
    appreciation_date: date | None = None
    notes: str | None = None


@app.get("/api/recipes/{slug}/executions")
async def list_executions(slug: str):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        recipe_id = await _get_recipe_id(conn, slug)
        rows = await conn.fetch(
            """SELECT id, date, cooked_by, rating, appreciated_by, appreciation_date, notes, created_at
               FROM recipe_execution WHERE recipe_id = $1 ORDER BY date DESC""",
            recipe_id,
        )
    result = []
    for r in rows:
        d = dict(r)
        _serialize_dates(d, ("date", "appreciation_date", "created_at"))
        result.append(d)
    return {"executions": result}


@app.post("/api/recipes/{slug}/executions")
async def add_execution(slug: str, body: ExecutionCreate):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        recipe_id = await _get_recipe_id(conn, slug)
        row = await conn.fetchrow(
            """INSERT INTO recipe_execution (recipe_id, date, cooked_by, rating, appreciated_by, appreciation_date, notes)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               RETURNING id, date, cooked_by, rating, appreciated_by, appreciation_date, notes, created_at""",
            recipe_id, body.date, body.cooked_by, body.rating,
            body.appreciated_by, body.appreciation_date, body.notes,
        )
        await conn.execute(
            "UPDATE recipe SET execution_count = execution_count + 1 WHERE id = $1",
            recipe_id,
        )
    d = dict(row)
    _serialize_dates(d, ("date", "appreciation_date", "created_at"))
    return d


@app.post("/api/seed-history")
async def seed_history():
    """Seed execution history from vault frontmatter and known data."""
    pool = await get_pool(DATABASE_DSN)

    history = [
        {
            "slug": "gratin-courge-spaghetti-pois-chiches-feta",
            "date": date(2026, 7, 28),
            "cooked_by": "Julien",
            "rating": 5,
            "appreciated_by": ["Julien", "Clémence", "Guillaume", "Virginie"],
            "appreciation_date": date(2026, 7, 28),
            "notes": "Unanimité 4/4. Premier plat validé par les beaux-parents. Lieu : Normandie.",
        },
        {
            "slug": "pancakes-banane-avoine",
            "date": date(2026, 5, 26),
            "cooked_by": "Julien",
            "rating": 5,
            "appreciated_by": ["Julien", "Clémence", "Léa", "Titouan"],
            "appreciation_date": date(2026, 5, 26),
            "notes": "Validée famille au premier test. Adoptée par les 4.",
        },
        {
            "slug": "salade-lentilles-froides-graines-courge",
            "date": date(2026, 7, 28),
            "cooked_by": "Julien",
            "rating": 5,
            "appreciated_by": ["Guillaume", "Virginie", "Clémence", "Julien"],
            "appreciation_date": date(2026, 7, 28),
            "notes": "Invités-validée. Substitutions : ail→gingembre, oignon blanc→rouge (Guillaume).",
        },
        {
            "slug": "ninja-creami-myrtilles-fromage-blanc",
            "date": date(2026, 7, 8),
            "cooked_by": "Julien",
            "rating": 5,
            "appreciated_by": ["Julien", "Clémence", "Léa", "Titouan"],
            "appreciation_date": date(2026, 7, 9),
            "notes": "Pot 1 journal Creami. Parfait après re-spin. Tout le monde adore.",
        },
    ]

    seeded = 0
    async with pool.acquire() as conn:
        for h in history:
            row = await conn.fetchrow("SELECT id FROM recipe WHERE slug = $1", h["slug"])
            if not row:
                continue
            recipe_id = row["id"]
            exists = await conn.fetchval(
                "SELECT 1 FROM recipe_execution WHERE recipe_id = $1 AND date = $2",
                recipe_id, h["date"],
            )
            if exists:
                continue
            await conn.execute(
                """INSERT INTO recipe_execution (recipe_id, date, cooked_by, rating, appreciated_by, appreciation_date, notes)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                recipe_id, h["date"], h["cooked_by"], h["rating"],
                h["appreciated_by"], h["appreciation_date"], h["notes"],
            )
            await conn.execute(
                "UPDATE recipe SET execution_count = GREATEST(execution_count, 1) WHERE id = $1",
                recipe_id,
            )
            seeded += 1

    return {"seeded": seeded, "total_entries": len(history)}


# ── Shopping ───────────────────────────────────────────────────────

@app.post("/api/shopping/import")
async def import_shopping_session():
    """Import shopping session from local JSON into PostgreSQL."""
    data_dir = Path(__file__).parent.parent / "data"
    files = sorted(data_dir.glob("shopping_choices_*.json"), reverse=True)
    if not files:
        raise HTTPException(404, "No shopping JSON found in data/")

    raw = json.loads(files[0].read_text(encoding="utf-8"))
    meta = raw["meta"]
    products = raw["products"]

    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO shopping_session (date, store, cart_id, covers, people, total, items_count, notes)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
               RETURNING id""",
            date.fromisoformat(meta["date"]), meta["store"], meta.get("cart_id"),
            meta.get("covers"), meta.get("people", []), meta.get("total"),
            meta.get("items_count"), meta.get("notes"),
        )
        session_id = row["id"]

        for p in products:
            chosen = p.get("product_chosen", {})
            alts = p.get("alternatives_considered", [])
            await conn.execute(
                """INSERT INTO shopping_product
                   (session_id, item_requested, product_name, brand, product_id,
                    price_unit, quantity_bought, total_price, status,
                    rationale, quantity_rationale, alternatives, lesson_learned)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                session_id, p["item_requested"],
                chosen.get("name", ""), chosen.get("brand"),
                chosen.get("product_id"), chosen.get("price_unit") or chosen.get("price"),
                chosen.get("quantity_bought", 1),
                chosen.get("total") or chosen.get("price"),
                p.get("status", "added"),
                p.get("rationale", ""),
                p.get("quantity_rationale"),
                json.dumps(alts) if alts else "[]",
                p.get("lesson_learned"),
            )

        prefs = raw.get("preferences", {})
        for exc in prefs.get("exclusions", []):
            await conn.execute(
                """INSERT INTO shopping_preference (pref_type, key, value, reason)
                   VALUES ('exclusion', $1, $2, $3)
                   ON CONFLICT (pref_type, key) DO UPDATE SET value=$2, reason=$3, updated_at=NOW()""",
                exc["product_type"], exc.get("alternative", ""), exc.get("reason"),
            )
        for buy in prefs.get("buy_elsewhere", []):
            await conn.execute(
                """INSERT INTO shopping_preference (pref_type, key, value, reason)
                   VALUES ('buy_elsewhere', $1, $2, $3)
                   ON CONFLICT (pref_type, key) DO UPDATE SET value=$2, reason=$3, updated_at=NOW()""",
                buy["product_type"], buy.get("where", ""), buy.get("reason"),
            )

    return {"imported": session_id, "products": len(products), "file": files[0].name}


@app.get("/api/shopping/preferences")
async def list_shopping_preferences():
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM shopping_preference WHERE active = TRUE ORDER BY pref_type, key"
        )
    return {"preferences": [dict(r) for r in rows]}


@app.get("/api/shopping/sessions")
async def list_shopping_sessions():
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM shopping_session ORDER BY date DESC LIMIT 20"
        )
    sessions = []
    for r in rows:
        d = dict(r)
        _serialize_dates(d, ("date", "created_at"))
        sessions.append(d)
    return {"sessions": sessions}


# ── Auchan Drive ───────────────────────────────────────────────────

class AuchanRemove(BaseModel):
    product_id: str
    token: str
    cart_id: str


@app.get("/api/auchan/product/{auchan_id}")
async def auchan_product_detail(auchan_id: str):
    from .auchan import scrape_product_detail
    from dataclasses import asdict
    url = f"https://www.auchan.fr/p/pr-{auchan_id}"
    detail = await scrape_product_detail(url)
    return asdict(detail)


@app.post("/api/auchan/remove")
async def auchan_remove_from_cart(body: AuchanRemove):
    from .auchan import AuchanClient
    client = AuchanClient(token=body.token, cart_id=body.cart_id)
    result = await client.remove_from_cart(body.product_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return {"removed": body.product_id, "cart": result}


@app.get("/health")
async def health():
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        version = await conn.fetchval("SELECT version()")
    return {"status": "ok", "db": version, "app_version": "2.0.0"}


# ── Helpers ─────────────────────────────────────────────────────────

def _recipe_to_dict(row) -> dict:
    d = dict(row)
    macros = {}
    for k in ("macros_kcal", "macros_protein", "macros_carbs", "macros_fat"):
        val = d.pop(k, None)
        if val is not None:
            macros[k.replace("macros_", "")] = val
    if macros:
        d["macros"] = macros
    _serialize_dates(d, ("created", "updated"))
    return d


# ── Static files (must be last) ────────────────────────────────────

WEB_DIR = Path(__file__).parent.parent / "web"
if WEB_DIR.is_dir():
    @app.get("/")
    async def index():
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/", StaticFiles(directory=str(WEB_DIR)), name="static")
