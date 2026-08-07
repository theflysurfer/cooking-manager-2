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
    sub_recipes TEXT[] DEFAULT '{}',
    body        TEXT,
    created     DATE,
    updated     DATE,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS menu (
    id          SERIAL PRIMARY KEY,
    slug        TEXT UNIQUE NOT NULL,
    title       TEXT NOT NULL,
    week_start  DATE,
    week_end    DATE,
    configuration TEXT,
    pattern_sport TEXT,
    status      TEXT NOT NULL DEFAULT 'proposed',
    linked_recipes TEXT[] DEFAULT '{}',
    meals       JSONB,
    body        TEXT,
    created     DATE,
    updated     DATE,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

-- Un repas = une ligne. C'est ce qui relie enfin le menu aux recettes, et ce
-- qui permet de filtrer les recettes par semaine.
--
-- ⚠️ La clé est (menu, jour, créneau), PAS (menu, recette) : une recette
-- refaite trois fois dans la semaine produit trois lignes. Dédoublonner sur la
-- recette perdrait deux repas — et les quantités qui vont avec.
--
-- `recipe_id` est NULLABLE **par conception** : un repas sans fiche
-- (« restes », « sandwich au marché ») reste un repas. Le forcer à pointer une
-- recette obligerait à inventer un rattachement — et acheter les ingrédients
-- de la mauvaise recette.
CREATE TABLE IF NOT EXISTS menu_meal (
    id          SERIAL PRIMARY KEY,
    menu_id     INTEGER NOT NULL REFERENCES menu(id) ON DELETE CASCADE,
    day         DATE,
    day_label   TEXT,
    position    INTEGER NOT NULL DEFAULT 0,
    slot        TEXT NOT NULL,
    dish        TEXT NOT NULL,
    recipe_id   INTEGER REFERENCES recipe(id) ON DELETE SET NULL,
    match_kind  TEXT,
    covers      INTEGER,
    UNIQUE (menu_id, position, slot)
);

CREATE INDEX IF NOT EXISTS menu_meal_recipe_idx ON menu_meal(recipe_id);

CREATE TABLE IF NOT EXISTS convive (
    id          SERIAL PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    constraints TEXT[] DEFAULT '{}',
    notes       TEXT,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS recipe_execution (
    id          SERIAL PRIMARY KEY,
    recipe_id   INTEGER NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
    date        DATE NOT NULL,
    cooked_by   TEXT,
    rating      INTEGER CHECK (rating >= 1 AND rating <= 5),
    appreciated_by TEXT[] DEFAULT '{}',
    appreciation_date DATE,
    notes       TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recipe_slug ON recipe(slug);
CREATE INDEX IF NOT EXISTS idx_recipe_status ON recipe(status);
CREATE INDEX IF NOT EXISTS idx_recipe_family ON recipe(family);
CREATE INDEX IF NOT EXISTS idx_recipe_tags ON recipe USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_execution_recipe ON recipe_execution(recipe_id);
CREATE INDEX IF NOT EXISTS idx_execution_date ON recipe_execution(date DESC);

CREATE TABLE IF NOT EXISTS shopping_session (
    id          SERIAL PRIMARY KEY,
    date        DATE NOT NULL,
    store       TEXT NOT NULL,
    cart_id     TEXT,
    covers      INTEGER,
    people      TEXT[] DEFAULT '{}',
    total       REAL,
    items_count INTEGER,
    notes       TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shopping_product (
    id              SERIAL PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES shopping_session(id) ON DELETE CASCADE,
    item_requested  TEXT NOT NULL,
    product_name    TEXT NOT NULL,
    brand           TEXT,
    product_id      TEXT,
    price_unit      REAL,
    quantity_bought  INTEGER DEFAULT 1,
    total_price     REAL,
    status          TEXT DEFAULT 'added',
    rationale       TEXT NOT NULL,
    quantity_rationale TEXT,
    alternatives    JSONB DEFAULT '[]',
    lesson_learned  TEXT,
    auchan_id       TEXT,
    nutriscore      TEXT,
    nutrition       JSONB,
    ingredients     TEXT,
    allergens       TEXT,
    characteristics JSONB,
    photo_url       TEXT,
    product_url     TEXT,
    weight          TEXT,
    price_per_kg    REAL,
    ean             TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shopping_preference (
    id          SERIAL PRIMARY KEY,
    pref_type   TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    reason      TEXT,
    active      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(pref_type, key)
);

CREATE INDEX IF NOT EXISTS idx_shopping_product_session ON shopping_product(session_id);
CREATE INDEX IF NOT EXISTS idx_shopping_preference_type ON shopping_preference(pref_type);

-- Ingrédients structurés, extraits du corps markdown des recettes.
-- `raw` est TOUJOURS conservé : une ligne que le parser n'a pas comprise reste
-- affichable telle quelle. Un ingrédient avalé en silence = un achat manqué.
-- `name_normalized` est la clé d'appariement avec le garde-manger.
CREATE TABLE IF NOT EXISTS recipe_ingredient (
    id          SERIAL PRIMARY KEY,
    recipe_id   INTEGER NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    raw         TEXT NOT NULL,
    qty_min     NUMERIC,
    qty_max     NUMERIC,
    unit        TEXT,
    name        TEXT NOT NULL,
    name_normalized TEXT NOT NULL DEFAULT '',
    is_optional BOOL NOT NULL DEFAULT FALSE,
    parsed      BOOL NOT NULL DEFAULT FALSE,
    UNIQUE (recipe_id, position)
);

CREATE TABLE IF NOT EXISTS recipe_step (
    id          SERIAL PRIMARY KEY,
    recipe_id   INTEGER NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    text        TEXT NOT NULL,
    UNIQUE (recipe_id, position)
);

CREATE INDEX IF NOT EXISTS idx_ingredient_recipe ON recipe_ingredient(recipe_id);
CREATE INDEX IF NOT EXISTS idx_ingredient_norm ON recipe_ingredient(name_normalized);
CREATE INDEX IF NOT EXISTS idx_step_recipe ON recipe_step(recipe_id);

-- Garde-manger : la DB est la source de vérité (pas le vault Markdown, qui n'est
-- qu'une source d'ingestion parmi d'autres — Auchan, voix, API).
-- Contrainte UNIQUE sur (name_normalized, section) : un produit par rayon.
-- Les items ajoutés par API/MCP vivent ici même si le vault ne les mentionne pas.
CREATE TABLE IF NOT EXISTS pantry_item (
    id                  SERIAL PRIMARY KEY,
    name                TEXT NOT NULL,
    name_normalized     TEXT NOT NULL,
    section             TEXT NOT NULL,
    qty_text            TEXT DEFAULT '',
    qty_value           NUMERIC,
    unit                TEXT,
    status              TEXT NOT NULL DEFAULT 'ok',
    xstatus             TEXT NOT NULL DEFAULT 'ok',
    perishable          BOOLEAN NOT NULL DEFAULT FALSE,
    entered_at          DATE,
    source              TEXT DEFAULT 'vault',
    shopping_product_id INTEGER REFERENCES shopping_product(id) ON DELETE SET NULL,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (name_normalized, section)
);

CREATE INDEX IF NOT EXISTS idx_pantry_item_status ON pantry_item(status);
CREATE INDEX IF NOT EXISTS idx_pantry_item_norm ON pantry_item(name_normalized);
CREATE INDEX IF NOT EXISTS idx_pantry_item_section ON pantry_item(section);
"""

MIGRATIONS_SQL = """
ALTER TABLE recipe ADD COLUMN IF NOT EXISTS body TEXT;
ALTER TABLE menu ADD COLUMN IF NOT EXISTS meals JSONB;
ALTER TABLE menu ADD COLUMN IF NOT EXISTS body TEXT;
ALTER TABLE recipe_execution ADD COLUMN IF NOT EXISTS appreciation_date DATE;

-- menu.slug : clé naturelle, sans laquelle l'ingestion ne peut pas dédoublonner
-- (elle se protégeait par un DELETE FROM menu qui détruisait les menus absents du vault).
-- Ajout en 3 temps : colonne nullable -> backfill -> contrainte, sinon l'ALTER échoue
-- sur les lignes existantes.
ALTER TABLE menu ADD COLUMN IF NOT EXISTS slug TEXT;
UPDATE menu SET slug = 'legacy-' || id::text WHERE slug IS NULL OR slug = '';
DO $mig$
BEGIN
    ALTER TABLE menu ADD CONSTRAINT menu_slug_key UNIQUE (slug);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN duplicate_object THEN NULL;
END $mig$;
ALTER TABLE menu ALTER COLUMN slug SET NOT NULL;

-- Auto-nettoyage : une ligne backfillée en 'legacy-N' disparaît dès que la vraie
-- (même titre, slug issu du vault) a été ingérée. Ne supprime jamais un menu
-- qui n'aurait pas de remplaçant.
DELETE FROM menu m
 WHERE m.slug LIKE 'legacy-%'
   AND EXISTS (SELECT 1 FROM menu o
                WHERE o.title = m.title AND o.slug NOT LIKE 'legacy-%');
ALTER TABLE shopping_product ADD COLUMN IF NOT EXISTS auchan_id TEXT;
ALTER TABLE shopping_product ADD COLUMN IF NOT EXISTS nutriscore TEXT;
ALTER TABLE shopping_product ADD COLUMN IF NOT EXISTS nutrition JSONB;
ALTER TABLE shopping_product ADD COLUMN IF NOT EXISTS ingredients TEXT;
ALTER TABLE shopping_product ADD COLUMN IF NOT EXISTS allergens TEXT;
ALTER TABLE shopping_product ADD COLUMN IF NOT EXISTS characteristics JSONB;
ALTER TABLE shopping_product ADD COLUMN IF NOT EXISTS photo_url TEXT;
ALTER TABLE shopping_product ADD COLUMN IF NOT EXISTS product_url TEXT;
ALTER TABLE shopping_product ADD COLUMN IF NOT EXISTS weight TEXT;
ALTER TABLE shopping_product ADD COLUMN IF NOT EXISTS price_per_kg REAL;

-- REAL = float4 : 3.8 stocké puis élargi en float8 à la lecture ressort en
-- 3.799999952316284, affiché tel quel dans l'UI. NUMERIC supprime la cause ;
-- l'arrondi à la sérialisation (_recipe_to_dict) couvre l'affichage.
ALTER TABLE recipe ALTER COLUMN macros_kcal    TYPE NUMERIC USING macros_kcal::numeric;
ALTER TABLE recipe ALTER COLUMN macros_protein TYPE NUMERIC USING macros_protein::numeric;
ALTER TABLE recipe ALTER COLUMN macros_carbs   TYPE NUMERIC USING macros_carbs::numeric;
ALTER TABLE recipe ALTER COLUMN macros_fat     TYPE NUMERIC USING macros_fat::numeric;
ALTER TABLE recipe ALTER COLUMN protein_density TYPE NUMERIC USING protein_density::numeric;
ALTER TABLE shopping_session ALTER COLUMN total TYPE NUMERIC USING total::numeric;
ALTER TABLE shopping_product ALTER COLUMN price_unit   TYPE NUMERIC USING price_unit::numeric;
ALTER TABLE shopping_product ALTER COLUMN total_price  TYPE NUMERIC USING total_price::numeric;
ALTER TABLE shopping_product ALTER COLUMN price_per_kg TYPE NUMERIC USING price_per_kg::numeric;
ALTER TABLE shopping_product ADD COLUMN IF NOT EXISTS ean TEXT;
ALTER TABLE menu_meal ADD COLUMN IF NOT EXISTS covers INTEGER;
ALTER TABLE recipe ADD COLUMN IF NOT EXISTS sub_recipes TEXT[] DEFAULT '{}';
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
        await conn.execute(MIGRATIONS_SQL)


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
