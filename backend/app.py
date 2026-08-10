"""FastAPI application — recipe browser + ingest trigger."""

import json
import re
from contextlib import asynccontextmanager
import datetime
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from cooking_manager.presence import HouseholdConfig, CustodyInfo, CanteenEntry

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


# Nombre de décimales par champ à la sortie de l'API. Les colonnes sont en NUMERIC
# (asyncpg rend des Decimal) : on arrondit ET on convertit en float ici, pour que
# l'UI n'ait jamais à s'en soucier. Sans ça, un ancien REAL ressortait en
# 3.799999952316284 et s'affichait tel quel.
_ROUNDING = {
    "macros_kcal": 1, "macros_protein": 1, "macros_carbs": 1, "macros_fat": 1,
    "kcal": 1, "protein": 1, "carbs": 1, "fat": 1,
    "protein_density": 3,
    "price_unit": 2, "total_price": 2, "price_per_kg": 2, "total": 2,
}


def _round_numeric(d: dict) -> dict:
    """Arrondit les champs numériques connus et normalise Decimal → float."""
    for key, digits in _ROUNDING.items():
        val = d.get(key)
        if val is None or isinstance(val, bool):
            continue
        try:
            d[key] = round(float(val), digits)
        except (TypeError, ValueError):
            continue
    return d


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
    menu: str | None = Query(default=None, description="slug de menu — restreint à la semaine"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    pool = await get_pool(DATABASE_DSN)
    clauses = []
    params = []
    idx = 1

    if menu:
        # ⚠️ EXISTS, pas de JOIN : une recette refaite trois fois dans la semaine
        # doit apparaître UNE fois dans le catalogue. Le nombre de fois est une
        # donnée de la recette (`occurrences`), pas une multiplication des lignes.
        clauses.append(
            f"EXISTS (SELECT 1 FROM menu_meal mm JOIN menu mu ON mu.id = mm.menu_id "
            f"WHERE mm.recipe_id = recipe.id AND mu.slug = ${idx})"
        )
        params.append(menu)
        idx += 1

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

    # Quand on filtre sur une semaine, le nombre de fois où la recette y revient
    # (et à quels créneaux) fait partie de la réponse : « 2× » est l'information
    # qui manque le plus quand on planifie.
    occurrences = ""
    if menu:
        occurrences = """,
               (SELECT COUNT(*) FROM menu_meal mm JOIN menu mu ON mu.id = mm.menu_id
                 WHERE mm.recipe_id = recipe.id AND mu.slug = $1) AS occurrences,
               (SELECT ARRAY_AGG(mm.day_label || ' · ' || mm.slot ORDER BY mm.position)
                  FROM menu_meal mm JOIN menu mu ON mu.id = mm.menu_id
                 WHERE mm.recipe_id = recipe.id AND mu.slug = $1) AS scheduled_at"""

    sql = f"""
        SELECT id, slug, title, status, recipe_type, family, servings,
               total_time_min, prep_time_min, cook_time_min,
               tags, compatible_constraints, sources, appreciated_by,
               applied_substitutions, mediterranean_criteria,
               construction_regime, execution_count, lieu_execution,
               macros_kcal, macros_protein, macros_carbs, macros_fat,
               protein_density, photo_url, created, updated{occurrences}
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
    """Fiche complète : métadonnées + ingrédients et étapes STRUCTURÉS.

    Le champ `body` (markdown brut) reste servi pour les notes libres, mais il
    n'est plus la source d'affichage principale — c'était lui qui produisait le
    mur de markdown en bas de la fiche.
    """
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM recipe WHERE slug = $1", slug)
        if not row:
            raise HTTPException(404, "Recipe not found")
        ingredients = await conn.fetch(
            """SELECT position, raw, qty_min, qty_max, unit, name,
                      name_normalized, is_optional, parsed
                 FROM recipe_ingredient WHERE recipe_id = $1 ORDER BY position""",
            row["id"],
        )
        steps = await conn.fetch(
            "SELECT position, text FROM recipe_step WHERE recipe_id = $1 ORDER BY position",
            row["id"],
        )

    data = _recipe_to_dict(row)
    data["ingredients"] = [
        _round_numeric({**dict(i), "qty_min": i["qty_min"], "qty_max": i["qty_max"]})
        for i in ingredients
    ]
    data["steps"] = [dict(s) for s in steps]
    return data


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
    slug: str | None = None
    week_start: datetime.date | None = None
    week_end: datetime.date | None = None
    configuration: str | None = None
    status: str = "proposed"
    linked_recipes: list[str] = []
    meals: list[dict] | None = None
    body: str | None = None


@app.post("/api/menus")
async def create_menu(menu: MenuCreate):
    """Créer ou mettre à jour un menu. Le slug est la clé naturelle : rejouer le
    même POST met à jour au lieu de dupliquer (et l'ingestion vault ne l'écrase
    plus, cf. suppression du DELETE FROM menu)."""
    from cooking_manager.normalizer import slugify

    slug = menu.slug or slugify(menu.title)
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO menu (slug, title, week_start, week_end, configuration, status,
                                linked_recipes, meals, body, created, updated)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, CURRENT_DATE, CURRENT_DATE)
               ON CONFLICT (slug) DO UPDATE SET
                   title=$2, week_start=$3, week_end=$4, configuration=$5, status=$6,
                   linked_recipes=$7, meals=$8::jsonb, body=$9, updated=CURRENT_DATE,
                   ingested_at=NOW()
               RETURNING id, slug, title, (xmax = 0) AS inserted""",
            slug, menu.title, menu.week_start, menu.week_end, menu.configuration,
            menu.status, menu.linked_recipes,
            json.dumps(menu.meals) if menu.meals else None,
            menu.body,
        )
    return {"id": row["id"], "slug": row["slug"], "title": row["title"],
            "created": row["inserted"]}


@app.get("/api/menus/{slug}/compatibility")
async def menu_compatibility(slug: str):
    """Contrôle de compatibilité alimentaire du menu, repas par repas.

    Croise DEUX choses qu'on ne peut pas séparer :
      * qui est réellement à table (référentiel de présence — garde alternée,
        vacances scolaires, absences) ;
      * ce que chacun ne peut pas manger (régimes, interdits, aversions).

    L'incident du 2026-08-04 tenait aux deux à la fois : des wraps au poulet
    devant une pescétarienne, ET une composition de table devinée depuis une
    grille valable « hors vacances scolaires » alors qu'on était en août.
    """
    from datetime import date as _date

    from cooking_manager.convives import check_meal, parse_convives
    from cooking_manager.presence import attendees, parse_referential
    from cooking_manager.vault import _parse_frontmatter, read_convives

    vault = Path(VAULT_ROOT)
    convives = {c.name: c for c in parse_convives(read_convives(vault).get("_body", ""))}

    presences = vault / "Presences.md"
    referential = parse_referential(
        _parse_frontmatter(presences)[1] if presences.exists() else ""
    )

    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT slug, title, meals FROM menu WHERE slug = $1", slug)
        if not row:
            raise HTTPException(404, f"Menu introuvable : {slug}")
        household = await load_household_config(conn)

    meals = row["meals"]
    if isinstance(meals, str):
        meals = json.loads(meals)

    checked, conflict_count = [], 0
    for meal in meals or []:
        for slot in ("breakfast", "lunch", "snack", "dinner"):
            dish = meal.get(slot)
            if not dish:
                continue
            try:
                day = _date.fromisoformat(meal["date"]) if meal.get("date") else None
            except (ValueError, TypeError):
                day = None

            present = attendees(day, slot, referential, household) if day else list(convives)
            conflicts = check_meal(dish, [convives[n] for n in present if n in convives])
            conflict_count += len(conflicts)
            checked.append({
                "day": meal.get("day"), "date": meal.get("date"), "slot": slot,
                "dish": dish, "attendees": present,
                "at_home": bool(present),
                "conflicts": [
                    {"convive": c.convive, "reason": c.reason, "matched": c.matched}
                    for c in conflicts
                ],
            })

    return {
        "slug": row["slug"], "title": row["title"],
        "meals_checked": len(checked), "conflicts": conflict_count,
        "convives_known": len(convives),
        "results": checked,
    }


async def _pantry_from_db():
    """Build a Pantry from the DB (source of truth since Phase 1)."""
    from cooking_manager.pantry import Pantry, PantryItem

    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT name, name_normalized, section, qty_text, qty_value, unit,
                      status, xstatus, entered_at
                 FROM pantry_item ORDER BY section, name"""
        )
        meta = await conn.fetchrow(
            "SELECT MAX(updated_at) AS last_updated FROM pantry_item"
        )

    last = meta["last_updated"]
    updated = last.date() if last and hasattr(last, "date") else last

    items = []
    for r in rows:
        items.append(PantryItem(
            rayon=r["section"],
            name=r["name"],
            name_normalized=r["name_normalized"],
            qty_text=r["qty_text"] or "",
            qty_value=float(r["qty_value"]) if r["qty_value"] is not None else None,
            unit=r["unit"],
            status=r["status"],
            xstatus=r["xstatus"] or "ok",
            entered_at=r["entered_at"],
        ))

    return Pantry(items=items, updated=updated)


@app.get("/api/pantry")
async def get_pantry():
    """Inventaire depuis la DB, groupé par rayon."""
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, name, name_normalized, section, qty_text, qty_value, unit,
                      status, xstatus, perishable, entered_at, source,
                      shopping_product_id, notes, updated_at
                 FROM pantry_item ORDER BY section, name"""
        )
        meta = await conn.fetchrow(
            "SELECT MAX(updated_at) AS last_updated, COUNT(*) AS total FROM pantry_item"
        )

    last_updated = meta["last_updated"]
    age_days = None
    is_stale = False
    if last_updated:
        age_days = (datetime.datetime.now(datetime.timezone.utc) - last_updated).days
        is_stale = age_days > 14

    rayons: dict[str, list] = {}
    for r in rows:
        rayons.setdefault(r["section"], []).append({
            "id": r["id"],
            "name": r["name"],
            "name_normalized": r["name_normalized"],
            "qty_text": r["qty_text"],
            "qty_value": float(r["qty_value"]) if r["qty_value"] is not None else None,
            "unit": r["unit"],
            "status": r["status"],
            "xstatus": r["xstatus"],
            "perishable": r["perishable"],
            "entered_at": r["entered_at"].isoformat() if r["entered_at"] else None,
            "source": r["source"],
            "notes": r["notes"],
        })

    return {
        "updated": last_updated.isoformat() if last_updated else None,
        "age_days": age_days,
        "is_stale": is_stale,
        "total": meta["total"],
        "rayons": [{"name": k, "items": v} for k, v in rayons.items()],
    }


@app.get("/api/menus/{slug}/shopping-list")
async def menu_shopping_list(
    slug: str, covers: int | None = None, from_date: str | None = None,
):
    """Menu → liste de courses différentielle, groupée par recette.

    Trois étapes, dans cet ordre :
      1. retrouver les recettes citées dans les repas du menu ;
      2. agréger leurs ingrédients, pondérés par convives / portions_base ;
      3. croiser chaque besoin avec le garde-manger réel.

    Le résultat n'est jamais un verdict silencieux : chaque ligne porte son
    `outcome` et sa `reason`, et l'état `inconnu` existe précisément pour que
    l'app demande au lieu de deviner.
    """
    from cooking_manager.pantry import build_needs, check_need

    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        menu = await conn.fetchrow(
            "SELECT slug, title, meals FROM menu WHERE slug = $1", slug)
        if not menu:
            raise HTTPException(404, f"Menu introuvable : {slug}")

        # Les repas sont reliés aux recettes à l'ingestion (`menu_meal`), plus
        # devinés à chaque appel : deux appels successifs donnaient auparavant
        # deux listes différentes si une recette venait d'être ajoutée.
        date_filter = ""
        params: list = [slug]
        if from_date:
            date_filter = " AND (mm.day IS NULL OR mm.day >= $2)"
            params.append(datetime.date.fromisoformat(from_date))

        rows = await conn.fetch(
            """SELECT mm.slot, mm.dish, mm.day_label, mm.match_kind, mm.covers,
                      r.id, r.slug, r.title, r.servings
                 FROM menu_meal mm
                 LEFT JOIN recipe r ON r.id = mm.recipe_id
                WHERE mm.menu_id = (SELECT id FROM menu WHERE slug = $1)"""
            + date_filter
            + " ORDER BY mm.position, mm.slot",
            *params,
        )

        matched, unmatched, leftovers = [], [], []
        for row in rows:
            if row["match_kind"] == "leftovers":
                # Repas de restes : sans fiche PAR CONCEPTION. Le compter comme
                # manquant ferait clignoter une alerte qu'on ne peut pas éteindre.
                leftovers.append({"day": row["day_label"], "slot": row["slot"],
                                  "dish": row["dish"]})
            elif row["id"] is None:
                unmatched.append({"day": row["day_label"], "slot": row["slot"],
                                  "dish": row["dish"]})
            else:
                # ⚠️ Pas de dédoublonnage : une recette refaite deux fois dans
                # la semaine doit peser deux fois dans les quantités.
                matched.append((row, row["dish"]))

        default_covers = covers or 4
        payload = []
        for recipe, _dish in matched:
            rows = await conn.fetch(
                """SELECT name, name_normalized, qty_min, qty_max, unit,
                          is_optional, parsed, raw
                     FROM recipe_ingredient WHERE recipe_id = $1 ORDER BY position""",
                recipe["id"],
            )
            meal_covers = recipe["covers"] if recipe["covers"] else default_covers
            base = recipe["servings"] or meal_covers
            ratio = meal_covers / base if base else 1.0
            payload.append((recipe["title"], [dict(r) for r in rows], ratio))

    needs = build_needs(payload)
    pantry = await _pantry_from_db()

    lines = []
    for need in needs:
        verdict = check_need(need, pantry)
        lines.append({
            "name": need.name,
            "name_normalized": need.name_normalized,
            "qty": round(need.qty, 2) if need.qty is not None else None,
            "unit": need.unit,
            "recipes": need.recipes,
            "shared": len(need.recipes) > 1,
            "is_optional": need.is_optional,
            "outcome": verdict.outcome,
            "reason": verdict.reason,
            "to_buy": verdict.to_buy,
            "assumed_empty": verdict.assumed_empty,
            "pantry": ({"name": verdict.pantry_item.name,
                        "qty_text": verdict.pantry_item.qty_text,
                        "status": verdict.pantry_item.status}
                       if verdict.pantry_item else None),
        })

    counts: dict[str, int] = {}
    for line in lines:
        counts[line["outcome"]] = counts.get(line["outcome"], 0) + 1

    return {
        "slug": menu["slug"], "title": menu["title"], "covers": default_covers,
        "recipes_matched": len({r["slug"] for r, _ in matched}),
        "meals_total": len(matched) + len(unmatched) + len(leftovers),
        "meals_unmatched": unmatched,
        "meals_leftovers": leftovers,
        "pantry": {"updated": pantry.updated.isoformat() if pantry.updated else None,
                   "age_days": pantry.age_days(), "is_stale": pantry.is_stale()},
        "counts": counts,
        "lines": lines,
    }



class PantryUpdate(BaseModel):
    """Un des 4 gestes du différentiel garde-manger."""
    item_name: str                    # nom EXACT de la ligne dans Garde-manger.md
    action: str                       # have | missing | partial | update
    qty_text: str | None = None       # requis pour `update`


@app.patch("/api/pantry")
async def update_pantry(body: PantryUpdate):
    """Écrit un geste dans `Garde-manger.md`.

    ⚠️ Écriture **ciblée ligne à ligne**, jamais de réécriture globale : le
    fichier est aussi lu par le family-dashboard et éditable depuis Obsidian,
    et une session parallèle peut le modifier entre-temps. Réécrire tout le
    fichier écraserait son travail sans un mot.

    ⚠️ L'app Dropbox desktop est désactivée : cette écriture ne remonte au cloud
    qu'après un bisync (`julien-vault-bisync`). Le champ `needs_bisync` du
    retour est là pour qu'on ne l'oublie pas.
    """
    actions = {"have", "missing", "partial", "update"}
    if body.action not in actions:
        raise HTTPException(400, f"action inconnue : {body.action} (attendu {actions})")
    if body.action == "update" and not body.qty_text:
        raise HTTPException(400, "`qty_text` est requis pour l'action `update`")

    path = Path(VAULT_ROOT) / "Garde-manger.md"
    if not path.exists():
        raise HTTPException(404, f"Garde-manger introuvable : {path}")

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    target, needle = None, body.item_name.strip().lower()
    for idx, line in enumerate(lines):
        if not line.lstrip().startswith("- "):
            continue
        head = re.split(r"\s+[—–]\s+", line.lstrip()[2:], maxsplit=1)[0]
        if re.sub(r"\*\*", "", head).strip().lower() == needle:
            target = idx
            break
    if target is None:
        raise HTTPException(404, f"Ligne introuvable dans le garde-manger : {body.item_name}")

    original = lines[target]
    today = datetime.date.today().isoformat()

    if body.action == "have":
        # Rien à changer : l'utilisateur confirme simplement le stock.
        return {"changed": False, "line": original.strip(), "needs_bisync": False}

    new_status = {"missing": "out", "partial": "low", "update": "ok"}[body.action]
    updated = re.sub(r"#\s*status\s*=\s*[\w\-àéèêëîïôöûü]+",
                     f"# status={new_status}", original)
    if "status=" not in updated:
        updated = updated.rstrip("\n") + f" # status={new_status}\n"

    if body.action == "update" and body.qty_text:
        # Remplacer la quantité, en préservant le nom et les annotations.
        parts = re.split(r"(\s+[—–]\s+)", updated.rstrip("\n"), maxsplit=1)
        if len(parts) == 3:
            tail = re.search(r"(\(entré[^)]*\))", parts[2])
            suffix = f" {tail.group(1)}" if tail else ""
            status = re.search(r"(#\s*status=[^\s]+.*)$", parts[2])
            updated = (f"{parts[0]}{parts[1]}{body.qty_text}{suffix} "
                       f"{status.group(1) if status else ''}".rstrip() + "\n")

    updated = re.sub(r"\(constaté [^)]*\)", "", updated).rstrip("\n")
    updated = f"{updated} (constaté {today})\n"

    lines[target] = updated
    path.write_text("".join(lines), encoding="utf-8")

    return {
        "changed": True,
        "before": original.strip(),
        "after": updated.strip(),
        "needs_bisync": True,
        "hint": "Lancer la skill julien-vault-bisync pour propager au cloud "
                "(l'app Dropbox desktop est désactivée).",
    }


# ── Pantry CRUD (DB-backed) ──────────────────────────────────────

class PantryItemCreate(BaseModel):
    name: str
    section: str
    qty_text: str = ""
    status: str = "ok"
    entered_at: datetime.date | None = None
    source: str = "manual"
    notes: str | None = None


class PantryItemUpdate(BaseModel):
    name: str | None = None
    section: str | None = None
    qty_text: str | None = None
    status: str | None = None
    xstatus: str | None = None
    entered_at: datetime.date | None = None
    notes: str | None = None


@app.post("/api/pantry/items")
async def create_pantry_item(body: PantryItemCreate):
    from cooking_manager.ingredients import normalize_name
    from cooking_manager.pantry import XSTATUS_MAP, PERISHABLE_HINTS

    name_normalized = normalize_name(body.name)
    if not name_normalized:
        raise HTTPException(400, "Nom vide après normalisation")

    xstatus = body.status
    status = XSTATUS_MAP.get(xstatus, body.status)
    perishable = any(h in body.section.lower() for h in PERISHABLE_HINTS)

    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                """INSERT INTO pantry_item
                   (name, name_normalized, section, qty_text, status, xstatus,
                    perishable, entered_at, source, notes)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                   RETURNING id, name, section, status""",
                body.name, name_normalized, body.section, body.qty_text,
                status, xstatus, perishable,
                body.entered_at or datetime.date.today(), body.source, body.notes,
            )
        except Exception as e:
            if "unique" in str(e).lower():
                raise HTTPException(
                    409, f"Item déjà existant : {body.name} dans {body.section}"
                ) from None
            raise
    return dict(row)


@app.get("/api/pantry/items/{item_id}")
async def get_pantry_item(item_id: int):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM pantry_item WHERE id = $1", item_id)
    if not row:
        raise HTTPException(404, f"Item introuvable : {item_id}")
    d = dict(row)
    _serialize_dates(d, ("entered_at", "created_at", "updated_at"))
    return d


@app.put("/api/pantry/items/{item_id}")
async def update_pantry_item(item_id: int, body: PantryItemUpdate):
    from cooking_manager.ingredients import normalize_name
    from cooking_manager.pantry import XSTATUS_MAP, PERISHABLE_HINTS

    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT * FROM pantry_item WHERE id = $1", item_id)
        if not existing:
            raise HTTPException(404, f"Item introuvable : {item_id}")

        name = body.name or existing["name"]
        section = body.section or existing["section"]
        qty_text = body.qty_text if body.qty_text is not None else existing["qty_text"]
        xstatus = body.xstatus or body.status or existing["xstatus"]
        status = XSTATUS_MAP.get(xstatus, xstatus)
        entered_at = body.entered_at or existing["entered_at"]
        notes = body.notes if body.notes is not None else existing["notes"]

        from cooking_manager.pantry import _parse_qty
        qty_value, unit = _parse_qty(qty_text)
        perishable = any(h in section.lower() for h in PERISHABLE_HINTS)

        await conn.execute(
            """UPDATE pantry_item SET
                   name=$1, name_normalized=$2, section=$3, qty_text=$4,
                   qty_value=$5, unit=$6, status=$7, xstatus=$8,
                   perishable=$9, entered_at=$10, notes=$11, updated_at=NOW()
               WHERE id=$12""",
            name, normalize_name(name), section, qty_text,
            float(qty_value) if qty_value is not None else None, unit,
            status, xstatus, perishable, entered_at, notes, item_id,
        )

    return {"id": item_id, "name": name, "status": status, "updated": True}


@app.delete("/api/pantry/items/{item_id}")
async def delete_pantry_item(item_id: int):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "DELETE FROM pantry_item WHERE id = $1 RETURNING id, name", item_id
        )
    if not row:
        raise HTTPException(404, f"Item introuvable : {item_id}")
    return {"deleted": row["name"], "id": row["id"]}


class PantryBulkItem(BaseModel):
    name: str
    section: str = "Frais — Légumes & Fruits"
    qty_text: str = ""


@app.post("/api/pantry/bulk")
async def bulk_upsert_pantry(items: list[PantryBulkItem]):
    """Upsert a batch of pantry items (vocal bulk inventory)."""
    from cooking_manager.ingredients import normalize_name
    from cooking_manager.pantry import PERISHABLE_HINTS, _parse_qty

    if not items:
        raise HTTPException(400, "Liste vide")
    if len(items) > 50:
        raise HTTPException(400, "50 items maximum par batch")

    pool = await get_pool(DATABASE_DSN)
    results = []
    async with pool.acquire() as conn:
        for item in items:
            name_normalized = normalize_name(item.name)
            if not name_normalized:
                results.append({"name": item.name, "status": "skipped", "reason": "nom vide"})
                continue

            qty_value, unit = _parse_qty(item.qty_text)
            perishable = any(h in item.section.lower() for h in PERISHABLE_HINTS)

            existing = await conn.fetchrow(
                "SELECT id FROM pantry_item WHERE name_normalized = $1 AND section = $2",
                name_normalized, item.section,
            )
            if existing:
                await conn.execute(
                    """UPDATE pantry_item SET
                           qty_text=$1, qty_value=$2, unit=$3, status='ok', xstatus='ok',
                           perishable=$4, updated_at=NOW(), source='voice'
                       WHERE id=$5""",
                    item.qty_text,
                    float(qty_value) if qty_value is not None else None,
                    unit, perishable, existing["id"],
                )
                results.append({
                    "id": existing["id"], "name": item.name,
                    "section": item.section, "status": "updated",
                })
            else:
                row = await conn.fetchrow(
                    """INSERT INTO pantry_item
                       (name, name_normalized, section, qty_text, qty_value, unit,
                        status, xstatus, perishable, entered_at, source)
                       VALUES ($1,$2,$3,$4,$5,$6,'ok','ok',$7,$8,'voice')
                       RETURNING id""",
                    item.name, name_normalized, item.section, item.qty_text,
                    float(qty_value) if qty_value is not None else None,
                    unit, perishable, datetime.date.today(),
                )
                results.append({
                    "id": row["id"], "name": item.name,
                    "section": item.section, "status": "created",
                })

    created = sum(1 for r in results if r.get("status") == "created")
    updated = sum(1 for r in results if r.get("status") == "updated")
    return {"results": results, "created": created, "updated": updated}


@app.get("/api/pantry/search")
async def search_pantry(q: str = Query(..., min_length=1)):
    """Recherche dans le garde-manger par nom (partiel, insensible à la casse)."""
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, name, name_normalized, section, qty_text, status, xstatus,
                      perishable, entered_at, source, notes
                 FROM pantry_item
                WHERE name ILIKE $1 OR name_normalized ILIKE $1
             ORDER BY name LIMIT 20""",
            f"%{q}%",
        )
    return {"results": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/menus/{slug}/meals")
async def list_menu_meals(slug: str):
    """Liste des repas structurés du menu, avec leur id pour édition."""
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        menu = await conn.fetchrow("SELECT id FROM menu WHERE slug = $1", slug)
        if not menu:
            raise HTTPException(404, f"Menu introuvable : {slug}")
        rows = await conn.fetch(
            """SELECT mm.id, mm.day, mm.day_label, mm.position, mm.slot,
                      mm.dish, mm.recipe_id, mm.match_kind, mm.covers,
                      r.slug AS recipe_slug, r.title AS recipe_title,
                      r.photo_url AS recipe_photo
                 FROM menu_meal mm
                 LEFT JOIN recipe r ON r.id = mm.recipe_id
                WHERE mm.menu_id = $1
             ORDER BY mm.position, mm.slot""",
            menu["id"],
        )
    meals = []
    for r in rows:
        d = dict(r)
        if d.get("day") and hasattr(d["day"], "isoformat"):
            d["day"] = d["day"].isoformat()
        meals.append(d)
    return {"slug": slug, "meals": meals}


class MealUpdate(BaseModel):
    recipe_slug: str | None = None
    dish: str | None = None
    covers: int | None = None


@app.patch("/api/menus/{slug}/meals/{meal_id}")
async def update_menu_meal(slug: str, meal_id: int, body: MealUpdate):
    """Changer la recette, l'intitulé et/ou le nombre de couverts d'un repas."""
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        menu = await conn.fetchrow("SELECT id FROM menu WHERE slug = $1", slug)
        if not menu:
            raise HTTPException(404, f"Menu introuvable : {slug}")
        meal = await conn.fetchrow(
            "SELECT id, dish, covers FROM menu_meal WHERE id = $1 AND menu_id = $2",
            meal_id, menu["id"],
        )
        if not meal:
            raise HTTPException(404, f"Repas introuvable : {meal_id}")

        recipe_id = None
        match_kind = None
        dish = meal["dish"]

        if body.recipe_slug:
            recipe = await conn.fetchrow(
                "SELECT id, title FROM recipe WHERE slug = $1", body.recipe_slug,
            )
            if not recipe:
                raise HTTPException(404, f"Recette introuvable : {body.recipe_slug}")
            recipe_id = recipe["id"]
            match_kind = "manual"
            dish = body.dish or recipe["title"]
        elif body.dish:
            dish = body.dish

        if body.covers is not None:
            await conn.execute(
                "UPDATE menu_meal SET covers = $1 WHERE id = $2",
                body.covers, meal_id,
            )

        if body.recipe_slug or body.dish:
            await conn.execute(
                """UPDATE menu_meal SET dish = $1, recipe_id = $2, match_kind = $3
                    WHERE id = $4""",
                dish, recipe_id, match_kind, meal_id,
            )

    return {"id": meal_id, "dish": dish, "recipe_id": recipe_id,
            "match_kind": match_kind, "covers": body.covers}


@app.delete("/api/menus/{slug}")
async def delete_menu(slug: str):
    """Supprimer un menu par son slug.

    Nécessaire depuis que l'ingestion ne fait plus de `DELETE FROM menu` :
    sans cet endpoint, un menu créé par l'API ne peut plus jamais partir.
    Les menus issus du vault reviendront à la prochaine ingestion — c'est le
    fichier qui fait foi, pas la base.
    """
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "DELETE FROM menu WHERE slug = $1 RETURNING id, slug", slug
        )
    if not row:
        raise HTTPException(404, f"Menu introuvable : {slug}")
    return {"deleted": row["slug"], "id": row["id"]}


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
    date: datetime.date
    cooked_by: str | None = None
    rating: int | None = None
    appreciated_by: list[str] = []
    appreciation_date: datetime.date | None = None
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
            "date": datetime.date(2026, 7, 28),
            "cooked_by": "Julien",
            "rating": 5,
            "appreciated_by": ["Julien", "Clémence", "Guillaume", "Virginie"],
            "appreciation_date": datetime.date(2026, 7, 28),
            "notes": "Unanimité 4/4. Premier plat validé par les beaux-parents. Lieu : Normandie.",
        },
        {
            "slug": "pancakes-banane-avoine",
            "date": datetime.date(2026, 5, 26),
            "cooked_by": "Julien",
            "rating": 5,
            "appreciated_by": ["Julien", "Clémence", "Léa", "Titouan"],
            "appreciation_date": datetime.date(2026, 5, 26),
            "notes": "Validée famille au premier test. Adoptée par les 4.",
        },
        {
            "slug": "salade-lentilles-froides-graines-courge",
            "date": datetime.date(2026, 7, 28),
            "cooked_by": "Julien",
            "rating": 5,
            "appreciated_by": ["Guillaume", "Virginie", "Clémence", "Julien"],
            "appreciation_date": datetime.date(2026, 7, 28),
            "notes": "Invités-validée. Substitutions : ail→gingembre, oignon blanc→rouge (Guillaume).",
        },
        {
            "slug": "ninja-creami-myrtilles-fromage-blanc",
            "date": datetime.date(2026, 7, 8),
            "cooked_by": "Julien",
            "rating": 5,
            "appreciated_by": ["Julien", "Clémence", "Léa", "Titouan"],
            "appreciation_date": datetime.date(2026, 7, 9),
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
            datetime.date.fromisoformat(meta["date"]), meta["store"], meta.get("cart_id"),
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


class ShoppingItemIn(BaseModel):
    item_requested: str
    product_name: str
    brand: str | None = None
    product_id: str | None = None
    price_unit: float | None = None
    quantity_bought: int = 1
    total_price: float | None = None
    status: str = "added"
    rationale: str = ""
    quantity_rationale: str | None = None
    alternatives: list = []
    lesson_learned: str | None = None


class ShoppingSessionMeta(BaseModel):
    date: str
    store: str
    cart_id: str | None = None
    covers: int | None = None
    people: list[str] = []
    total: float | None = None
    items_count: int | None = None
    notes: str | None = None


class PersistCartRequest(BaseModel):
    meta: ShoppingSessionMeta
    items: list[ShoppingItemIn]


@app.post("/api/shopping/persist-cart")
async def persist_cart_with_nutrition(body: PersistCartRequest):
    """Persist a cart/order into shopping_session + shopping_product."""

    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO shopping_session (date, store, cart_id, covers, people, total, items_count, notes)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
               RETURNING id""",
            datetime.date.fromisoformat(body.meta.date), body.meta.store, body.meta.cart_id,
            body.meta.covers, body.meta.people, body.meta.total,
            body.meta.items_count, body.meta.notes,
        )
        session_id = row["id"]

        for item in body.items:
            await conn.execute(
                """INSERT INTO shopping_product
                   (session_id, item_requested, product_name, brand, product_id,
                    price_unit, quantity_bought, total_price, status,
                    rationale, quantity_rationale, alternatives, lesson_learned,
                    auchan_id, nutriscore, nutrition, ingredients, allergens,
                    characteristics, photo_url, product_url, weight, price_per_kg, ean)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,
                           $14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24)""",
                session_id, item.item_requested, item.product_name, item.brand,
                item.product_id, item.price_unit, item.quantity_bought,
                item.total_price, item.status, item.rationale,
                item.quantity_rationale, json.dumps(item.alternatives),
                item.lesson_learned,
                None, None, None, None, None, None, None, None, None, None, None,
            )

    return {
        "session_id": session_id,
        "items_persisted": len(body.items),
    }


@app.get("/api/shopping/sessions/{session_id}/products")
async def list_session_products(session_id: int):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT product_name, brand, item_requested, price_unit, quantity_bought,
                      total_price, nutriscore, nutrition, ingredients, allergens,
                      photo_url, product_url, weight, price_per_kg, ean, status
                 FROM shopping_product WHERE session_id = $1
                 ORDER BY id""",
            session_id,
        )
    products = []
    for r in rows:
        d = _round_numeric(dict(r))
        if d.get("nutrition") and isinstance(d["nutrition"], str):
            d["nutrition"] = json.loads(d["nutrition"])
        products.append(d)
    return {"products": products, "total": len(products)}


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
        d = _round_numeric(dict(r))
        _serialize_dates(d, ("date", "created_at"))
        sessions.append(d)
    return {"sessions": sessions}


# ── Voice intent endpoints ─────────────────────────────────────────

class BlacklistBody(BaseModel):
    product: str
    reason: str | None = None


@app.post("/api/shopping/preferences")
async def add_shopping_preference(body: BlacklistBody):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO shopping_preference (pref_type, key, value, reason)
               VALUES ('blacklist', $1, $2, $3)
               ON CONFLICT (pref_type, key) DO UPDATE
               SET value = EXCLUDED.value, reason = EXCLUDED.reason,
                   active = TRUE, updated_at = NOW()""",
            body.product, body.reason or "vocal", body.reason,
        )
    return {"ok": True, "product": body.product}


class RecipeNoteBody(BaseModel):
    note: str


@app.post("/api/recipes/{slug}/note")
async def add_recipe_note(slug: str, body: RecipeNoteBody):
    today = datetime.date.today()
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        recipe_id = await _get_recipe_id(conn, slug)
        row = await conn.fetchrow(
            """INSERT INTO recipe_execution (recipe_id, date, notes)
               VALUES ($1, $2, $3)
               RETURNING id""",
            recipe_id, today, body.note,
        )
    return {"ok": True, "execution_id": row["id"]}


class StepEditBody(BaseModel):
    text: str


@app.patch("/api/recipes/{slug}/steps/{position}")
async def edit_recipe_step(slug: str, position: int, body: StepEditBody):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        recipe_id = await _get_recipe_id(conn, slug)
        result = await conn.execute(
            "UPDATE recipe_step SET text = $1 WHERE recipe_id = $2 AND position = $3",
            body.text, recipe_id, position,
        )
        if result == "UPDATE 0":
            raise HTTPException(404, f"Step {position} not found")
    return {"ok": True, "position": position}


class FeedbackBody(BaseModel):
    dish: str
    convive: str | None = None
    liked: bool = True
    comment: str | None = None


@app.post("/api/feedback")
async def add_meal_feedback(body: FeedbackBody):
    today = datetime.date.today()
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM recipe WHERE LOWER(title) LIKE '%' || LOWER($1) || '%' LIMIT 1",
            body.dish,
        )
        if not row:
            return {"ok": False, "reason": f"Aucune recette trouvée pour « {body.dish} »"}
        recipe_id = row["id"]
        appreciated_by = [body.convive] if body.convive and body.liked else []
        notes = body.comment
        if not body.liked and body.convive:
            notes = (notes or "") + f" ({body.convive} n'a pas aimé)"
        await conn.fetchrow(
            """INSERT INTO recipe_execution (recipe_id, date, appreciated_by, appreciation_date, notes)
               VALUES ($1, $2, $3, $4, $5)
               RETURNING id""",
            recipe_id, today, appreciated_by, today if appreciated_by else None, notes,
        )
    return {"ok": True, "dish": body.dish}


class LeftoverBody(BaseModel):
    ingredient: str
    quantity: str | None = None
    shelf_life_days: int | None = None


@app.post("/api/pantry/leftover")
async def add_pantry_leftover(body: LeftoverBody):
    from cooking_manager.ingredients import normalize_name
    normalized = normalize_name(body.ingredient)
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO pantry_item (name, name_normalized, section, qty_text, status, source)
               VALUES ($1, $2, 'Restes', $3, 'ok', 'voice')
               ON CONFLICT (name_normalized, section) DO UPDATE
               SET qty_text = EXCLUDED.qty_text, status = 'ok', updated_at = NOW()""",
            body.ingredient, normalized, body.quantity or "",
        )
    return {"ok": True, "ingredient": body.ingredient}


# ── Multi-drive search ────────────────────────────────────────────

@app.get("/api/drives/{store}/stores")
async def drive_stores(store: str, postal_code: str = Query(..., min_length=4)):
    """Find nearby stores for a given enseigne + postal code."""
    from dataclasses import asdict

    if store == "leclerc":
        try:
            from leclerc_drive.stores import find_stores as leclerc_find  # type: ignore[import-untyped]
        except ImportError:
            raise HTTPException(501, "leclerc_drive not installed") from None
        stores = await leclerc_find(postal_code)
        return {"stores": [asdict(s) for s in stores]}

    raise HTTPException(400, "Enseigne inconnue, choix : leclerc")


@app.get("/api/drives/{store}/search")
async def drive_search(store: str, q: str = Query(..., min_length=1)):
    from .drives import search_store, SUPPORTED_STORES
    from dataclasses import asdict
    if store not in SUPPORTED_STORES:
        raise HTTPException(400, f"Enseigne inconnue, choix : {', '.join(SUPPORTED_STORES)}")
    results = await search_store(store, q)
    return {"products": [asdict(p) for p in results]}


class MapIngredientsBody(BaseModel):
    store: str
    ingredients: list[dict]


@app.post("/api/drives/map-ingredients")
async def drive_map_ingredients(body: MapIngredientsBody):
    from .drives import map_ingredients, SUPPORTED_STORES
    if body.store not in SUPPORTED_STORES:
        raise HTTPException(400, f"Enseigne inconnue, choix : {', '.join(SUPPORTED_STORES)}")
    mappings = await map_ingredients(body.store, body.ingredients)
    return {"mappings": mappings, "store": body.store}


class CompareBody(BaseModel):
    ingredients: list[dict]


@app.post("/api/drives/compare")
async def drive_compare(body: CompareBody):
    """Map ingredients on available stores and return results."""
    from .drives import map_ingredients

    leclerc_mappings = await map_ingredients("leclerc", body.ingredients)

    def _total(mappings: list[dict]) -> float:
        s = 0.0
        for m in mappings:
            sel = m.get("selected", -1)
            results = m.get("results", [])
            if 0 <= sel < len(results):
                p = results[sel].get("price")
                if p is not None:
                    s += p
        return round(s, 2)

    return {
        "leclerc": {"mappings": leclerc_mappings, "total": _total(leclerc_mappings)},
    }


# ── Voice / STT ───────────────────────────────────────────────────

@app.post("/api/audio")
async def voice_audio(file: UploadFile):
    """Audio → transcription → intent JSON. Pipeline complet."""
    from .stt import process_audio

    audio_bytes = await file.read()
    content_type = file.content_type or "audio/webm"
    try:
        result = await process_audio(audio_bytes, content_type)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from None
    return result


class IntentRequest(BaseModel):
    text: str


@app.post("/api/intent")
async def voice_intent(body: IntentRequest):
    """Texte → intent JSON (sans passer par l'audio)."""
    from .stt import interpret

    try:
        intent = await interpret(body.text)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from None
    return {"transcript": body.text, "intent": intent}


@app.get("/health")
async def health():
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        version = await conn.fetchval("SELECT version()")
    return {"status": "ok", "db": version, "app_version": "2.0.0"}


# ── Helpers ─────────────────────────────────────────────────────────

def _recipe_to_dict(row) -> dict:
    d = _round_numeric(dict(row))
    macros = {}
    for k in ("macros_kcal", "macros_protein", "macros_carbs", "macros_fat"):
        val = d.pop(k, None)
        if val is not None:
            macros[k.replace("macros_", "")] = val
    if macros:
        d["macros"] = macros
    _serialize_dates(d, ("created", "updated"))
    return d


# ── Tablée : person, household, relationship ───────────────────────

class PersonCreate(BaseModel):
    name: str
    full_name: str | None = None
    circle: str = "occasional"
    role: str = "adult"
    diet: str = "omnivore"
    dislikes: list[str] = []
    forbidden: list[str] = []
    notes: str | None = None
    default_attendance: str = "never"

class PersonUpdate(BaseModel):
    full_name: str | None = None
    circle: str | None = None
    role: str | None = None
    diet: str | None = None
    dislikes: list[str] | None = None
    forbidden: list[str] | None = None
    notes: str | None = None
    default_attendance: str | None = None
    is_active: bool | None = None

class RelationshipCreate(BaseModel):
    person_id: int
    related_id: int
    type: str

class CustodyScheduleCreate(BaseModel):
    person_id: int
    pattern: str = "alternating_weeks"
    reference_date: str
    reference_present: bool = True
    notes: str | None = None

class CanteenScheduleCreate(BaseModel):
    person_id: int
    weekday: int
    slot: str = "lunch"
    active_outside_holidays: bool = True


@app.get("/api/persons")
async def list_persons(circle: str | None = None, active_only: bool = True):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        where, params = ["1=1"], []
        if circle:
            params.append(circle)
            where.append(f"circle = ${len(params)}")
        if active_only:
            where.append("is_active")
        rows = await conn.fetch(
            f"SELECT * FROM person WHERE {' AND '.join(where)} ORDER BY circle, name",
            *params,
        )
    return [_round_numeric(dict(r)) for r in rows]


@app.post("/api/persons", status_code=201)
async def create_person(body: PersonCreate):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO person (name, full_name, circle, role, diet, dislikes,
                                   forbidden, notes, default_attendance)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING *""",
            body.name, body.full_name, body.circle, body.role, body.diet,
            body.dislikes, body.forbidden, body.notes, body.default_attendance,
        )
    return dict(row)


@app.get("/api/persons/{person_id}")
async def get_person(person_id: int):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM person WHERE id = $1", person_id)
    if not row:
        raise HTTPException(404, "Person not found")
    return dict(row)


@app.patch("/api/persons/{person_id}")
async def update_person(person_id: int, body: PersonUpdate):
    sets, params = [], [person_id]
    for fld, val in body.model_dump(exclude_unset=True).items():
        params.append(val)
        sets.append(f"{fld} = ${len(params)}")
    if not sets:
        raise HTTPException(400, "Nothing to update")
    sets.append("updated_at = NOW()")
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE person SET {', '.join(sets)} WHERE id = $1 RETURNING *", *params,
        )
    if not row:
        raise HTTPException(404, "Person not found")
    return dict(row)


@app.delete("/api/persons/{person_id}", status_code=204)
async def delete_person(person_id: int):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM person WHERE id = $1", person_id)
    if result == "DELETE 0":
        raise HTTPException(404, "Person not found")


# ── Households ──

@app.get("/api/households")
async def list_households():
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        households = await conn.fetch("SELECT * FROM household ORDER BY is_primary DESC, name")
        result = []
        for h in households:
            members = await conn.fetch(
                """SELECT hm.membership, p.id, p.name, p.role, p.circle
                   FROM household_member hm JOIN person p ON p.id = hm.person_id
                   WHERE hm.household_id = $1""",
                h["id"],
            )
            d = dict(h)
            d["members"] = [dict(m) for m in members]
            result.append(d)
    return result


@app.post("/api/households/{household_id}/members", status_code=201)
async def add_household_member(
    household_id: int, person_id: int = Query(...), membership: str = "resident",
):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO household_member (household_id, person_id, membership)
               VALUES ($1, $2, $3) ON CONFLICT DO NOTHING""",
            household_id, person_id, membership,
        )
    return {"ok": True}


@app.delete("/api/households/{household_id}/members/{person_id}", status_code=204)
async def remove_household_member(household_id: int, person_id: int):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM household_member WHERE household_id = $1 AND person_id = $2",
            household_id, person_id,
        )


# ── Relationships ──

@app.get("/api/relationships")
async def list_relationships():
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT r.*, p1.name AS person_name, p2.name AS related_name
               FROM relationship r
               JOIN person p1 ON p1.id = r.person_id
               JOIN person p2 ON p2.id = r.related_id""",
        )
    return [dict(r) for r in rows]


@app.post("/api/relationships", status_code=201)
async def create_relationship(body: RelationshipCreate):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO relationship (person_id, related_id, type)
               VALUES ($1, $2, $3)
               ON CONFLICT (person_id, related_id, type) DO NOTHING
               RETURNING *""",
            body.person_id, body.related_id, body.type,
        )
    return dict(row) if row else {"ok": True, "note": "already exists"}


@app.delete("/api/relationships/{rel_id}", status_code=204)
async def delete_relationship(rel_id: int):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM relationship WHERE id = $1", rel_id)


# ── Custody & canteen schedules ──

@app.get("/api/custody-schedules")
async def list_custody_schedules():
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT cs.*, p.name AS person_name
               FROM custody_schedule cs JOIN person p ON p.id = cs.person_id""",
        )
    return [_round_numeric(dict(r)) for r in rows]


@app.post("/api/custody-schedules", status_code=201)
async def create_custody_schedule(body: CustodyScheduleCreate):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO custody_schedule (person_id, pattern, reference_date,
                                            reference_present, notes)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (person_id) DO UPDATE SET
                   pattern = EXCLUDED.pattern, reference_date = EXCLUDED.reference_date,
                   reference_present = EXCLUDED.reference_present, notes = EXCLUDED.notes
               RETURNING *""",
            body.person_id, body.pattern,
            datetime.date.fromisoformat(body.reference_date),
            body.reference_present, body.notes,
        )
    return dict(row)


@app.get("/api/canteen-schedules")
async def list_canteen_schedules():
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT cs.*, p.name AS person_name
               FROM canteen_schedule cs JOIN person p ON p.id = cs.person_id""",
        )
    return [dict(r) for r in rows]


@app.post("/api/canteen-schedules", status_code=201)
async def create_canteen_schedule(body: CanteenScheduleCreate):
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO canteen_schedule (person_id, weekday, slot, active_outside_holidays)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (person_id, weekday, slot) DO UPDATE SET
                   active_outside_holidays = EXCLUDED.active_outside_holidays
               RETURNING *""",
            body.person_id, body.weekday, body.slot, body.active_outside_holidays,
        )
    return dict(row)


# ── HouseholdConfig from DB (bridge to presence.py) ──

async def load_household_config(conn) -> HouseholdConfig:

    adults_rows = await conn.fetch(
        "SELECT name FROM person WHERE circle = 'household' AND role = 'adult' AND is_active",
    )
    children_rows = await conn.fetch(
        """SELECT p.name, cs.pattern, cs.reference_date, cs.reference_present
           FROM person p LEFT JOIN custody_schedule cs ON cs.person_id = p.id
           WHERE p.circle = 'household' AND p.role = 'child' AND p.is_active""",
    )
    canteen_rows = await conn.fetch(
        """SELECT p.name, cs.weekday, cs.slot, cs.active_outside_holidays
           FROM canteen_schedule cs JOIN person p ON p.id = cs.person_id
           WHERE p.is_active""",
    )

    adults = tuple(r["name"] for r in adults_rows)
    children = []
    for r in children_rows:
        kwargs: dict = {"name": r["name"]}
        if r["pattern"]:
            kwargs["pattern"] = r["pattern"]
            kwargs["reference_date"] = r["reference_date"]
            kwargs["reference_present"] = r["reference_present"]
        children.append(CustodyInfo(**kwargs))

    canteen = [
        CanteenEntry(name=r["name"], weekday=r["weekday"],
                     slot=r["slot"], active_outside_holidays=r["active_outside_holidays"])
        for r in canteen_rows
    ]

    if not adults:
        return HouseholdConfig()
    return HouseholdConfig(adults=adults, children=children, canteen=canteen)


# ── Seed données initiales ──

SEED_PERSONS = [
    {"name": "Julien",   "circle": "household", "role": "adult", "default_attendance": "always"},
    {"name": "Clémence", "circle": "household", "role": "adult", "default_attendance": "always",
     "diet": "pescetarian", "forbidden": ["oeuf dur", "oeuf poché", "oeuf au plat", "oeuf mollet"]},
    {"name": "Léa",      "circle": "household", "role": "child", "default_attendance": "scheduled",
     "forbidden": ["oeuf dur", "oeuf poché", "oeuf au plat", "oeuf mollet"], "dislikes": ["mais"]},
    {"name": "Titouan",  "circle": "household", "role": "child", "default_attendance": "scheduled"},
]

SEED_RELATIONSHIPS = [
    ("Julien", "Léa",      "parent_of"),
    ("Julien", "Titouan",  "parent_of"),
    ("Clémence", "Léa",    "parent_of"),
    ("Clémence", "Titouan","parent_of"),
    ("Julien", "Clémence", "partner"),
    ("Léa",    "Titouan",  "sibling"),
]

SEED_CUSTODY_REFERENCE = datetime.date(2026, 3, 3)
SEED_CANTEEN_WEEKDAYS = [1, 3, 4]  # mardi, jeudi, vendredi


@app.post("/api/seed")
async def seed_household():
    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        created_persons = 0
        for p in SEED_PERSONS:
            result = await conn.execute(
                """INSERT INTO person (name, circle, role, diet, dislikes, forbidden,
                                       default_attendance)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   ON CONFLICT (name, circle) DO UPDATE SET
                       role = EXCLUDED.role, diet = EXCLUDED.diet,
                       dislikes = EXCLUDED.dislikes, forbidden = EXCLUDED.forbidden,
                       default_attendance = EXCLUDED.default_attendance, updated_at = NOW()""",
                p["name"], p["circle"], p["role"],
                p.get("diet", "omnivore"), p.get("dislikes", []),
                p.get("forbidden", []), p["default_attendance"],
            )
            if "INSERT" in result:
                created_persons += 1

        hh = await conn.fetchrow(
            "INSERT INTO household (name, is_primary) VALUES ('Foyer', TRUE) "
            "ON CONFLICT DO NOTHING RETURNING id",
        )
        hh_id = hh["id"] if hh else (
            await conn.fetchval("SELECT id FROM household WHERE is_primary")
        )

        for p in SEED_PERSONS:
            pid = await conn.fetchval(
                "SELECT id FROM person WHERE name = $1 AND circle = 'household'", p["name"],
            )
            if pid:
                await conn.execute(
                    "INSERT INTO household_member (household_id, person_id, membership) "
                    "VALUES ($1, $2, 'resident') ON CONFLICT DO NOTHING",
                    hh_id, pid,
                )

        created_rels = 0
        for name1, name2, rel_type in SEED_RELATIONSHIPS:
            p1 = await conn.fetchval("SELECT id FROM person WHERE name=$1 AND circle='household'", name1)
            p2 = await conn.fetchval("SELECT id FROM person WHERE name=$1 AND circle='household'", name2)
            if p1 and p2:
                r = await conn.execute(
                    "INSERT INTO relationship (person_id, related_id, type) "
                    "VALUES ($1,$2,$3) ON CONFLICT DO NOTHING", p1, p2, rel_type,
                )
                if "INSERT" in r:
                    created_rels += 1

        created_custody = 0
        for p in SEED_PERSONS:
            if p["role"] != "child":
                continue
            pid = await conn.fetchval(
                "SELECT id FROM person WHERE name=$1 AND circle='household'", p["name"],
            )
            if pid:
                r = await conn.execute(
                    "INSERT INTO custody_schedule (person_id, pattern, reference_date, reference_present) "
                    "VALUES ($1, 'alternating_weeks', $2, TRUE) ON CONFLICT (person_id) DO NOTHING",
                    pid, SEED_CUSTODY_REFERENCE,
                )
                if "INSERT" in r:
                    created_custody += 1

        created_canteen = 0
        for p in SEED_PERSONS:
            if p["role"] != "child":
                continue
            pid = await conn.fetchval(
                "SELECT id FROM person WHERE name=$1 AND circle='household'", p["name"],
            )
            if not pid:
                continue
            for wd in SEED_CANTEEN_WEEKDAYS:
                r = await conn.execute(
                    "INSERT INTO canteen_schedule (person_id, weekday, slot, active_outside_holidays) "
                    "VALUES ($1, $2, 'lunch', TRUE) ON CONFLICT DO NOTHING",
                    pid, wd,
                )
                if "INSERT" in r:
                    created_canteen += 1

    return {
        "persons": created_persons,
        "household_id": hh_id,
        "relationships": created_rels,
        "custody_schedules": created_custody,
        "canteen_schedules": created_canteen,
    }


# ── Static files (must be last) ────────────────────────────────────

WEB_DIR = Path(__file__).parent.parent / "web"
if WEB_DIR.is_dir():
    @app.get("/")
    async def index():
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/", StaticFiles(directory=str(WEB_DIR)), name="static")
