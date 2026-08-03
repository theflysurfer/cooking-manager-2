"""PostgreSQL connection pool and schema management."""

import asyncpg

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS recipe (
    id          SERIAL PRIMARY KEY,
    slug        TEXT UNIQUE NOT NULL,
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'draft',
    recipe_type TEXT,
    family      TEXT,
    servings    INTEGER,
    total_time_min INTEGER,
    prep_time_min  INTEGER,
    cook_time_min  INTEGER,
    tags        TEXT[] DEFAULT '{}',
    compatible_constraints TEXT[] DEFAULT '{}',
    sources     TEXT[] DEFAULT '{}',
    appreciated_by TEXT[] DEFAULT '{}',
    applied_substitutions TEXT[] DEFAULT '{}',
    mediterranean_criteria INTEGER[] DEFAULT '{}',
    construction_regime TEXT,
    execution_count INTEGER DEFAULT 0,
    lieu_execution TEXT,
    macros_kcal   REAL,
    macros_protein REAL,
    macros_carbs  REAL,
    macros_fat    REAL,
    protein_density REAL,
    photo_url   TEXT,
    created     DATE,
    updated     DATE,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS menu (
    id          SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    week_start  DATE,
    week_end    DATE,
    configuration TEXT,
    pattern_sport TEXT,
    status      TEXT NOT NULL DEFAULT 'proposed',
    linked_recipes TEXT[] DEFAULT '{}',
    created     DATE,
    updated     DATE,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS convive (
    id          SERIAL PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    constraints TEXT[] DEFAULT '{}',
    notes       TEXT,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recipe_slug ON recipe(slug);
CREATE INDEX IF NOT EXISTS idx_recipe_status ON recipe(status);
CREATE INDEX IF NOT EXISTS idx_recipe_family ON recipe(family);
CREATE INDEX IF NOT EXISTS idx_recipe_tags ON recipe USING GIN(tags);
"""

_pool: asyncpg.Pool | None = None


async def get_pool(dsn: str) -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    return _pool


async def init_schema(dsn: str) -> None:
    pool = await get_pool(dsn)
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
