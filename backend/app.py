"""FastAPI application — recipe browser + ingest trigger."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
        from fastapi import HTTPException
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
    return {"menus": [dict(r) for r in rows]}


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
