# Cooking Manager 2

Web app to browse and filter family recipes, plan weekly menus, and generate shopping lists. PostgreSQL is the single source of truth (ADR 0022) — the Obsidian vault is disconnected.

Designed for kitchen use on iPad mini 2 (Safari 12.5.8).

Live: `https://cooking.srv759970.hstgr.cloud`

## Features

- **Recipe browser** — filter by type, family, tags, dietary constraints; view photos, macros, ingredients, steps
- **Weekly menus** — written straight to the database (`POST /api/menus`), with per-meal recipe linking, photos and covers adjustment
- **Shopping list** — auto-generated from menu recipes × covers, with "remaining items" toggle (filters past days)
- **Dietary compatibility** — checks who's at the table (custody schedule × school holidays × absences) against each person's constraints
- **Voice commands** — speech-to-text (Deepgram) + LLM intent classification (Groq) for hands-free recipe search, servings adjustment, recipe swap, product blacklisting, recipe notes, step editing, meal feedback, and pantry leftovers (Safari 14.5+ only)
- **Table feedback** — record what each person thought of a dish, whether to cook it again, and
  what to fix; a menu is a *plan*, so each meal also carries a **tri-state** `served` (unknown /
  eaten / never cooked). Entered from the iPad, no `curl` required
- **Dietary preferences** — a third tier between hard bans and dislikes: minimize, maximize, cap
  (with value, unit and scope), rotate, no-restriction. They **weigh without blocking**: the menu
  compatibility endpoint counts them and reports `preferences_breached` — plus
  `preferences_unmeasurable`, because a rule whose target no ingredient carries, or a `cap` in
  grams counted in meals, reports a zero that measures nothing (ADR 0023)
- **Effort bands** — every dish is read from its *steps*, not its clock: `hands_off`,
  `light_hands_on`, `hands_on`, `project`. A 50-minute stew leaves your hands free; a 35-minute
  risotto does not. Weeknight dinners that do not fit are listed (ADR 0024)
- **Pantry management** — track what's in stock, mark leftovers
- **Cookbook import** — photograph a printed recipe page; a vision model transcribes it, the
  house parser structures the ingredients, and the draft is **reviewed before** it is written to
  the database. Nothing is written until you validate it.
- **Computed macros** — totals derived from the parsed ingredients, combining three sources by
  precedence (verified brand sheet › drive product label › ANSES CIQUAL generic). Reports its
  own **coverage**: a partial sum is never presented as a recipe total.

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI + asyncpg |
| Frontend | Vanilla JS SPA — zero build, static files served by FastAPI |
| Database | PostgreSQL (`postgresql-shared` Docker container) |
| Deploy | systemd + nginx on VPS, port 8795 |
| Voice | Deepgram (STT) + Groq LLM (intent) |

## Setup

```bash
# Prerequisites: Python 3.12+, PostgreSQL (or Docker postgresql-shared)

# Install
pip install .

# Run
python -m cooking_manager serve --port 8795

# Re-link menu meals to recipes (reads nothing from disk since ADR 0022)
curl -X POST http://localhost:8795/api/ingest
```

Environment variables:

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL DSN (`postgresql://cooking:...@localhost/cooking_manager`) |
| `VAULT_ROOT` | No | Legacy — still set in the systemd unit, read by nothing since ADR 0022 |
| `DEEPGRAM_API_KEY` | For voice | Deepgram STT API key |
| `GROQ_API_KEY` | For voice | Groq LLM API key |

## Data Source

**PostgreSQL only** (ADR 0022). Recipes, menus, people, pantry and shopping all live in the
database; nothing is read from the Obsidian vault.

| Table | Content |
|---|---|
| `recipe` / `recipe_ingredient` / `recipe_step` | Recipes, written by `POST /api/recipes` |
| `menu` / `menu_meal` | Weekly menus, written by `POST /api/menus` |
| `person` / `household_member` | Dietary profiles, and who is a resident of the household |
| `pantry_item` / `pantry_alias` | Pantry stock |
| `shopping_preference` | Products and brands refused at purchase |

`POST /api/ingest` no longer reads the filesystem: it re-links `menu_meal` rows to their recipes.

## API

### Recipes
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/recipes` | List recipes (with filters) |
| GET | `/api/recipes/{slug}` | Recipe detail |
| GET | `/api/recipes/{slug}/compatibility` | Dietary check **at a table**: `?convives=A,B` · `?day=YYYY-MM-DD&slot=dinner` · default = household residents (ADR 0025) |
| GET | `/api/filters` | Available filter values |
| GET | `/api/recipes/{slug}/executions` | Cooking history |
| POST | `/api/recipes/{slug}/executions` | Log a cooking execution |
| POST | `/api/recipes/{slug}/note` | Add a note to a recipe |
| PATCH | `/api/recipes/{slug}/steps/{position}` | Edit a recipe step |
| POST | `/api/recipes/parse-url` | Extract a recipe from a URL — returns it as-is, persists nothing |
| POST | `/api/recipes/import/url` | Extract a recipe from a URL **into a reviewable draft** (same review flow as book pages) |

### Menus
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/menus` | List menus |
| POST | `/api/menus` | Create a menu |
| DELETE | `/api/menus/{slug}` | Delete a menu |
| GET | `/api/menus/{slug}/meals` | Meals for a menu |
| PATCH | `/api/menus/{slug}/meals/{id}` | Update a meal (recipe, covers) |
| GET | `/api/menus/{slug}/compatibility` | Dietary check on **ingredients**, per meal — conflicts (each with `membership` and `repaired`), engine `repairs`, `unrepaired`, `preferences`, `meals_without_protein` (chacun avec `secondary` — l'apport protéique hors rotation), `weeknight_too_heavy` |
| GET | `/api/menus/{slug}/shopping-list` | Generate shopping list (`?covers=N&from_date=YYYY-MM-DD`) — each line carries `outcome`, `merged_from` and `purchase` (measured / countable / dose / unresolved) |

### Shopping
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/shopping/validate-cart` | Confront a cart with refused products — `ok:false` blocks checkout |
| POST | `/api/shopping/import` | Import a shopping session |
| POST | `/api/shopping/persist-cart` | Persist + enrich cart items (nutrition, nutriscore, allergens) |
| GET | `/api/shopping/sessions` | List shopping sessions |
| GET | `/api/shopping/preferences` | Product preferences (blacklist, favorites) |
| POST | `/api/shopping/preferences` | Add a product preference (blacklist/favorite) |

### Voice & Feedback
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/audio` | Audio → STT → LLM intent → action |
| POST | `/api/intent` | Text → LLM intent → action |
| POST | `/api/feedback` | Log meal feedback (rating, comment) |

### Pantry (DB-backed)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/pantry` | Pantry contents grouped by section |
| POST | `/api/pantry/items` | Add a pantry item |
| GET | `/api/pantry/items/{id}` | Item detail |
| PUT | `/api/pantry/items/{id}` | Update item (status, qty, notes) |
| DELETE | `/api/pantry/items/{id}` | Remove item |
| GET | `/api/pantry/search?q=` | Search items by name |
| POST | `/api/pantry/leftover` | Mark a pantry item as leftover |
| PATCH | `/api/pantry` | Update an item **by name** — 409 on homonyms, use `PUT /items/{id}` |

### Food reference (no frontend — curl, MCP or script)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/food` | List foods with their macro-form count (`?q=` filters) |
| POST | `/api/food` | Create a food (key derived from the name when omitted) |
| GET | `/api/food/{key}` | Food detail: forms + linked products |
| PUT | `/api/food/{key}` | Update a food |
| DELETE | `/api/food/{key}` | Delete a food — forms cascade, products are detached |
| GET | `/api/food/{key}/form` | List a food's macro forms |
| POST | `/api/food/{key}/form` | Upsert a form — `(food_key, label)` is the key |
| DELETE | `/api/food/{key}/form/{label}` | Remove one form |
| GET | `/api/product` | List products (`?q=`, `?unlinked=true`) |
| PATCH | `/api/product/{id}` | Link `food_key`, fix name/brand/nature/status |

Macros live in `food_form`, one row per form (`lentille` × `crues`/`cuites`) — never in `food`.
Three explicit refusals rather than a silent success: unknown `status` → **422**, unknown
`food_key` → **404**, linking a `composite` product → **422** (a composite carries its own
macros, ADR 0016).

### Other
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ingest` | Re-link `menu_meal` rows to their recipes (reads no file since ADR 0022) |
| GET | `/api/stats` | Dashboard stats |
| GET | `/health` | Health check |

## MCP Servers

### Cooking Manager MCP

Local MCP server for LLM access to pantry, recipes, and menus:

```bash
python -m backend.cooking_mcp  # stdio transport
```

10 tools: `pantry_list`, `pantry_search`, `pantry_add`, `pantry_update`, `pantry_remove`, `shopping_list`, `recipe_search`, `recipe_detail`, `menu_current`, `pantry_ingest`.

## Deploy

```bash
ssh srv759970 'cd /opt/cooking-manager-2 && git pull && .venv/bin/pip install -q . && sudo systemctl restart cooking-manager'
```

## Architecture

```
cooking_manager/       # Pure domain — no network I/O
  normalizer.py        # FR frontmatter → canonical EN, slugs, dates
  ingredients.py       # Markdown body → structured ingredients + steps
  convives.py          # Dietary profiles + compatibility checks
  presence.py          # Who's at the table (custody × holidays × absences)
  substitutions.py     # 47 context-aware swap rules; experience beats the rule
  parts.py             # Splits a conflicting line into household share + substitute share
  preferences.py       # cap/rotate/minimize/maximize, and what cannot be measured
  effort.py            # Effort band read from the steps; weeknight verdict
  bans.py              # Products and brands refused at purchase
backend/               # FastAPI + DB schema + ingestion
  stt.py               # Voice pipeline: Deepgram STT + Groq LLM intent
  cooking_mcp.py       # FastMCP server (stdio) — pantry, recipes, menus
web/                   # Frontend: index.html + style.css + app.js
tests/                 # Unit tests · iOS 12 compat gate · e2e (opt-in)
deploy/                # systemd unit, nginx config, install script
data/                  # Shopping sessions + photo prompt (versioned)
```

## Browser Compatibility

The frontend targets **Safari 12.5.8** (iPad mini 2 used in the kitchen). The iOS 12 compatibility gate is enforced on every commit touching `web/`. Voice features require Safari 14.5+ and are hidden on older browsers.
