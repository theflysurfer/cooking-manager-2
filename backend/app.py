"""FastAPI application — recipe browser + ingest trigger."""

from contextlib import asynccontextmanager
from pathlib import Path

from datetime import date

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import DATABASE_DSN, VAULT_ROOT
from .db import get_pool, init_schema, close_pool
from .ingest import ingest


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
    import json as _json
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM menu ORDER BY week_start DESC")
    menus = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("meals"), str):
            d["meals"] = _json.loads(d["meals"])
        for key in ("created", "updated", "week_start", "week_end"):
            if d.get(key) and hasattr(d[key], "isoformat"):
                d[key] = d[key].isoformat()
        menus.append(d)
    return {"menus": menus}


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
        recipe = await conn.fetchrow("SELECT id FROM recipe WHERE slug = $1", slug)
        if not recipe:
            raise HTTPException(404, "Recipe not found")
        rows = await conn.fetch(
            """SELECT id, date, cooked_by, rating, appreciated_by, appreciation_date, notes, created_at
               FROM recipe_execution WHERE recipe_id = $1 ORDER BY date DESC""",
            recipe["id"],
        )
    return {"executions": [dict(r) for r in rows]}


@app.post("/api/recipes/{slug}/executions")
async def add_execution(slug: str, body: ExecutionCreate):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        recipe = await conn.fetchrow("SELECT id FROM recipe WHERE slug = $1", slug)
        if not recipe:
            raise HTTPException(404, "Recipe not found")
        row = await conn.fetchrow(
            """INSERT INTO recipe_execution (recipe_id, date, cooked_by, rating, appreciated_by, appreciation_date, notes)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               RETURNING id, date, cooked_by, rating, appreciated_by, appreciation_date, notes, created_at""",
            recipe["id"], body.date, body.cooked_by, body.rating,
            body.appreciated_by, body.appreciation_date, body.notes,
        )
        await conn.execute(
            "UPDATE recipe SET execution_count = execution_count + 1 WHERE id = $1",
            recipe["id"],
        )
    return dict(row)


@app.post("/api/seed-history")
async def seed_history():
    """Seed execution history from vault frontmatter and known data."""
    from datetime import date as D
    pool = await get_pool(DATABASE_DSN)

    history = [
        {
            "slug": "gratin-courge-spaghetti-pois-chiches-feta",
            "date": D(2026, 7, 28),
            "cooked_by": "Julien",
            "rating": 5,
            "appreciated_by": ["Julien", "Clémence", "Guillaume", "Virginie"],
            "appreciation_date": D(2026, 7, 28),
            "notes": "Unanimité 4/4. Premier plat validé par les beaux-parents. Lieu : Normandie.",
        },
        {
            "slug": "pancakes-banane-avoine",
            "date": D(2026, 5, 26),
            "cooked_by": "Julien",
            "rating": 5,
            "appreciated_by": ["Julien", "Clémence", "Léa", "Titouan"],
            "appreciation_date": D(2026, 5, 26),
            "notes": "Validée famille au premier test. Adoptée par les 4.",
        },
        {
            "slug": "salade-lentilles-froides-graines-courge",
            "date": D(2026, 7, 28),
            "cooked_by": "Julien",
            "rating": 5,
            "appreciated_by": ["Guillaume", "Virginie", "Clémence", "Julien"],
            "appreciation_date": D(2026, 7, 28),
            "notes": "Invités-validée. Substitutions : ail→gingembre, oignon blanc→rouge (Guillaume).",
        },
        {
            "slug": "ninja-creami-myrtilles-fromage-blanc",
            "date": D(2026, 7, 8),
            "cooked_by": "Julien",
            "rating": 5,
            "appreciated_by": ["Julien", "Clémence", "Léa", "Titouan"],
            "appreciation_date": D(2026, 7, 9),
            "notes": "Pot 1 journal Creami. Parfait après re-spin. Tout le monde adore.",
        },
    ]

    seeded = 0
    async with pool.acquire() as conn:
        for h in history:
            recipe = await conn.fetchrow("SELECT id FROM recipe WHERE slug = $1", h["slug"])
            if not recipe:
                continue
            exists = await conn.fetchval(
                "SELECT 1 FROM recipe_execution WHERE recipe_id = $1 AND date = $2",
                recipe["id"], h["date"],
            )
            if exists:
                continue
            await conn.execute(
                """INSERT INTO recipe_execution (recipe_id, date, cooked_by, rating, appreciated_by, appreciation_date, notes)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                recipe["id"], h["date"], h["cooked_by"], h["rating"],
                h["appreciated_by"], h["appreciation_date"], h["notes"],
            )
            await conn.execute(
                "UPDATE recipe SET execution_count = GREATEST(execution_count, 1) WHERE id = $1",
                recipe["id"],
            )
            seeded += 1

    return {"seeded": seeded, "total_entries": len(history)}


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
    for key in ("created", "updated"):
        if d.get(key) and hasattr(d[key], "isoformat"):
            d[key] = d[key].isoformat()
    return d


# ── Static files (must be last) ────────────────────────────────────

WEB_DIR = Path(__file__).parent.parent / "web"
if WEB_DIR.is_dir():
    @app.get("/")
    async def index():
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/", StaticFiles(directory=str(WEB_DIR)), name="static")
