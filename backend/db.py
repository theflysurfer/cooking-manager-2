"""PostgreSQL connection pool and schema management."""

import asyncpg

SCHEMA_SQL = """
-- recipe, recipe_ingredient, recipe_step, recipe_execution are owned by
-- recipe-manager (port 8796). CM2 reads/writes them as a colocataire but
-- does not create them. Requires: After=recipe-manager.service in systemd.

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

-- ═══════════════════════════════════════════════════════════════════════
-- Tablée — qui mange à quel repas
--
-- Remplace le booléen at_home et les constantes ADULTS/CHILDREN en dur
-- dans presence.py. La table `convive` reste pour rétrocompatibilité ;
-- `person` en est le successeur fonctionnel.
-- ═══════════════════════════════════════════════════════════════════════

-- person : registre universel de quiconque peut s'asseoir à table.
-- Un seul registre, quel que soit le cercle (foyer, famille, ami, ponctuel).
CREATE TABLE IF NOT EXISTS person (
    id                  SERIAL PRIMARY KEY,
    name                TEXT NOT NULL,
    full_name           TEXT,
    circle              TEXT NOT NULL DEFAULT 'occasional'
                        CHECK (circle IN ('household', 'extended_family', 'friend', 'occasional')),
    role                TEXT NOT NULL DEFAULT 'adult'
                        CHECK (role IN ('adult', 'child', 'caregiver')),
    diet                TEXT NOT NULL DEFAULT 'omnivore',
    dislikes            TEXT[] DEFAULT '{}',
    forbidden           TEXT[] DEFAULT '{}',
    diet_exceptions     TEXT[] DEFAULT '{}',
    notes               TEXT,
    default_attendance  TEXT NOT NULL DEFAULT 'never'
                        CHECK (default_attendance IN ('always', 'never', 'scheduled')),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (name, circle)
);

-- relationship : liens entre personnes (parent/enfant, conjoint, fratrie).
-- Stocké dans un seul sens : parent_of = person_id est le parent.
-- L'inverse se déduit (« les enfants de Paul » = WHERE type='parent_of'
-- AND person_id = Paul).
CREATE TABLE IF NOT EXISTS relationship (
    id          SERIAL PRIMARY KEY,
    person_id   INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    related_id  INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    type        TEXT NOT NULL CHECK (type IN ('parent_of', 'partner', 'sibling')),
    UNIQUE (person_id, related_id, type),
    CHECK (person_id != related_id)
);

CREATE INDEX IF NOT EXISTS idx_relationship_person ON relationship(person_id);
CREATE INDEX IF NOT EXISTS idx_relationship_related ON relationship(related_id);

-- household : un foyer = un groupe de personnes qui vivent ensemble.
-- Le foyer principal (is_primary) fournit les résidents par défaut.
-- D'autres foyers (« chez Paul ») servent à modéliser la garde croisée
-- et les séjours (« vacances chez les grands-parents »).
CREATE TABLE IF NOT EXISTS household (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    is_primary  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_household_one_primary
    ON household (is_primary) WHERE is_primary;

CREATE TABLE IF NOT EXISTS household_member (
    household_id INTEGER NOT NULL REFERENCES household(id) ON DELETE CASCADE,
    person_id    INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    membership   TEXT NOT NULL DEFAULT 'resident'
                 CHECK (membership IN ('resident', 'regular_guest')),
    PRIMARY KEY (household_id, person_id)
);

-- person_group : raccourci nommé pour ajouter plusieurs personnes d'un coup
-- (« la famille Martin » = 4 person_id). auto_generated = créé depuis les
-- relations (ex. « les grands-parents » = tous les person avec
-- relationship parent_of vers un adulte du foyer principal).
CREATE TABLE IF NOT EXISTS person_group (
    id              SERIAL PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    auto_generated  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS person_group_member (
    group_id    INTEGER NOT NULL REFERENCES person_group(id) ON DELETE CASCADE,
    person_id   INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, person_id)
);

-- custody_schedule : garde alternée par enfant. Remplace les constantes
-- CUSTODY_REFERENCE_WEEK et CHILDREN en dur dans presence.py.
-- Chaque enfant peut avoir son propre rythme et sa propre date de référence
-- (garde croisée : les enfants du conjoint viennent les semaines inverses).
CREATE TABLE IF NOT EXISTS custody_schedule (
    id                  SERIAL PRIMARY KEY,
    person_id           INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    pattern             TEXT NOT NULL DEFAULT 'alternating_weeks'
                        CHECK (pattern IN ('alternating_weeks', 'specific_days', 'always')),
    reference_date      DATE NOT NULL,
    reference_present   BOOLEAN NOT NULL DEFAULT TRUE,
    weekday_override    JSONB,
    notes               TEXT,
    UNIQUE (person_id)
);

-- canteen_schedule : cantine par enfant et par jour. Remplace le test
-- « day.weekday() in (1, 3, 4) » en dur dans presence.py.
-- active_outside_holidays = TRUE signifie que la cantine n'existe QUE
-- hors vacances scolaires (le comportement actuel pour tous les enfants).
CREATE TABLE IF NOT EXISTS canteen_schedule (
    id                      SERIAL PRIMARY KEY,
    person_id               INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    weekday                 INTEGER NOT NULL CHECK (weekday >= 0 AND weekday <= 6),
    slot                    TEXT NOT NULL DEFAULT 'lunch',
    active_outside_holidays BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (person_id, weekday, slot)
);

-- meal_attendance : la tablée effective — qui mange quoi quand.
-- Calculée automatiquement depuis les schedules (source='computed'),
-- modifiable manuellement ('manual') ou par commande vocale ('voice').
-- extra_headcount couvre les « +3 anonymes sans profil ».
-- person_id est nullable : un extra_headcount sans person_id = invités anonymes.
CREATE TABLE IF NOT EXISTS meal_attendance (
    id              SERIAL PRIMARY KEY,
    menu_id         INTEGER REFERENCES menu(id) ON DELETE CASCADE,
    day             DATE NOT NULL,
    slot            TEXT NOT NULL CHECK (slot IN ('breakfast', 'lunch', 'snack', 'dinner')),
    person_id       INTEGER REFERENCES person(id) ON DELETE SET NULL,
    source          TEXT NOT NULL DEFAULT 'computed'
                    CHECK (source IN ('computed', 'manual', 'voice')),
    extra_headcount INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_meal_attendance_menu_day ON meal_attendance(menu_id, day, slot);
CREATE INDEX IF NOT EXISTS idx_meal_attendance_person ON meal_attendance(person_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_meal_attendance_unique
    ON meal_attendance(menu_id, day, slot, person_id) WHERE person_id IS NOT NULL;

-- school_period : vacances scolaires. Remplace le tableau §Vacances de
-- Presences.md — la trame de présence (cantine) en dépend, donc la DB doit
-- en être la source, pas un Markdown lu à la volée.
CREATE TABLE IF NOT EXISTS school_period (
    id          SERIAL PRIMARY KEY,
    label       TEXT NOT NULL,
    start_date  DATE NOT NULL,
    end_date    DATE NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- absence : une personne absente sur une période. slot NULL = toute la
-- journée ; slot renseigné = un seul créneau (« déjeune au bureau ce midi »).
-- Remplace le tableau §Absences de Presences.md.
CREATE TABLE IF NOT EXISTS absence (
    id          SERIAL PRIMARY KEY,
    person_id   INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    start_date  DATE NOT NULL,
    end_date    DATE NOT NULL,
    slot        TEXT CHECK (slot IN ('breakfast', 'lunch', 'snack', 'dinner')),
    reason      TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_absence_person ON absence(person_id);
CREATE INDEX IF NOT EXISTS idx_absence_dates ON absence(start_date, end_date);

-- stay : un séjour hors du domicile principal (vacances, week-end).
-- C'est le modèle qui MANQUAIT et qui causait le bug Bègles (F.30) : une
-- « absence » du foyer principal était lue comme « pas de repas à préparer »,
-- alors qu'on cuisine sur place. Un stay dit : ces personnes sont présentes
-- et à table sur cette période, quelle que soit la trame de garde/cantine.
--   cooking = TRUE  → on cuisine sur place (location, camping) — F.30
--   cooking = FALSE → pas de cuisine (hôtel, club vacances) — F.31
-- Un stay avec cooking=TRUE court-circuite la trame ET les absences : ses
-- membres sont à table pour tous les repas du séjour.
CREATE TABLE IF NOT EXISTS stay (
    id          SERIAL PRIMARY KEY,
    label       TEXT NOT NULL,
    start_date  DATE NOT NULL,
    end_date    DATE NOT NULL,
    location    TEXT,
    cooking     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stay_dates ON stay(start_date, end_date);

CREATE TABLE IF NOT EXISTS stay_member (
    stay_id     INTEGER NOT NULL REFERENCES stay(id) ON DELETE CASCADE,
    person_id   INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    PRIMARY KEY (stay_id, person_id)
);
"""

MIGRATIONS_SQL = """
-- diet_exceptions : ce que le régime interdit mais que CETTE personne mange.
-- Sans cette colonne, un régime est un absolu — or Clémence est pescétarienne
-- ET mange du boudin. Le contrôle bloquait un plat qu'elle accepte, et le seul
-- contournement était de mentir sur son régime.
ALTER TABLE person ADD COLUMN IF NOT EXISTS diet_exceptions TEXT[] DEFAULT '{}';

-- recipe column migrations are owned by recipe-manager.
ALTER TABLE menu ADD COLUMN IF NOT EXISTS meals JSONB;
ALTER TABLE menu ADD COLUMN IF NOT EXISTS body TEXT;

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

ALTER TABLE shopping_session ALTER COLUMN total TYPE NUMERIC USING total::numeric;
ALTER TABLE shopping_product ALTER COLUMN price_unit   TYPE NUMERIC USING price_unit::numeric;
ALTER TABLE shopping_product ALTER COLUMN total_price  TYPE NUMERIC USING total_price::numeric;
ALTER TABLE shopping_product ALTER COLUMN price_per_kg TYPE NUMERIC USING price_per_kg::numeric;
ALTER TABLE shopping_product ADD COLUMN IF NOT EXISTS ean TEXT;
ALTER TABLE menu_meal ADD COLUMN IF NOT EXISTS covers INTEGER;

-- household_member: rename role → membership (avoids confusion with person.role)
DO $rename_hm$
BEGIN
    ALTER TABLE household_member RENAME COLUMN role TO membership;
EXCEPTION
    WHEN undefined_column THEN NULL;
END $rename_hm$;

-- household: guarantee at most one primary
CREATE UNIQUE INDEX IF NOT EXISTS idx_household_one_primary
    ON household (is_primary) WHERE is_primary;

-- meal_attendance: prevent duplicate person per meal slot
CREATE UNIQUE INDEX IF NOT EXISTS idx_meal_attendance_unique
    ON meal_attendance(menu_id, day, slot, person_id) WHERE person_id IS NOT NULL;

-- ═══════════════════════════════════════════════════════════════════════
-- Migration tablée : convive → person + seed données initiales
-- ═══════════════════════════════════════════════════════════════════════

-- Migrer les convives existants vers person (idempotent).
-- Le champ constraints stocke « diet:X », « avoid:Y », « dislike:Z ».
INSERT INTO person (name, circle, role, diet, dislikes, forbidden, notes, default_attendance)
SELECT
    c.name,
    CASE WHEN c.notes = 'invité récurrent' THEN 'extended_family' ELSE 'household' END,
    'adult',
    COALESCE((
        SELECT REPLACE(unnest, 'diet:', '')
        FROM unnest(c.constraints)
        WHERE unnest LIKE 'diet:%'
        LIMIT 1
    ), 'omnivore'),
    ARRAY(SELECT REPLACE(unnest, 'dislike:', '') FROM unnest(c.constraints) WHERE unnest LIKE 'dislike:%'),
    ARRAY(SELECT REPLACE(unnest, 'avoid:', '') FROM unnest(c.constraints) WHERE unnest LIKE 'avoid:%'),
    c.notes,
    CASE WHEN c.notes = 'invité récurrent' THEN 'never' ELSE 'always' END
FROM convive c
WHERE NOT EXISTS (SELECT 1 FROM person p WHERE p.name = c.name)
ON CONFLICT DO NOTHING;

-- Seed le foyer principal (idempotent).
INSERT INTO household (name, is_primary)
SELECT 'Foyer', TRUE
WHERE NOT EXISTS (SELECT 1 FROM household WHERE is_primary);

-- Rattacher les membres du foyer au household principal.
INSERT INTO household_member (household_id, person_id, membership)
SELECT h.id, p.id, 'resident'
FROM household h, person p
WHERE h.is_primary AND p.circle = 'household'
ON CONFLICT DO NOTHING;
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
