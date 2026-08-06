# Cooking Manager 2

Web app to browse and filter family recipes from an Obsidian vault, plan weekly menus, generate shopping lists, and order groceries on Auchan Drive.

Designed for kitchen use on iPad mini 2 (Safari 12.5.8).

Live: `https://cooking.srv759970.hstgr.cloud`

## Features

- **Recipe browser** — filter by type, family, tags, dietary constraints; view photos, macros, ingredients, steps
- **Weekly menus** — ingested from Obsidian vault, with per-meal recipe linking and covers adjustment
- **Shopping list** — auto-generated from menu recipes × covers, with "remaining items" toggle (filters past days)
- **Auchan Drive** — search products, manage cart, persist purchases with nutritional enrichment (nutriscore, allergens, ingredients via Auchan scraping + Open Food Facts)
- **Dietary compatibility** — checks who's at the table (custody schedule × school holidays × absences) against each person's constraints
- **Voice commands** — speech-to-text (Deepgram) + LLM intent classification (Groq) for hands-free recipe search, servings adjustment, recipe swap (Safari 14.5+ only)
- **Pantry management** — track what's in stock, mark leftovers

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

# Ingest recipes from vault
curl -X POST http://localhost:8795/api/ingest
```

Environment variables:

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL DSN (`postgresql://cooking:...@localhost/cooking_manager`) |
| `VAULT_PATH` | Yes | Path to Obsidian vault `Noyau/Cuisine/` directory |
| `AUCHAN_TOKEN` | For shopping | Bearer JWT from Auchan Drive (expires frequently) |
| `AUCHAN_CART_ID` | For shopping | Cart UUID from Auchan Drive |
| `DEEPGRAM_API_KEY` | For voice | Deepgram STT API key |
| `GROQ_API_KEY` | For voice | Groq LLM API key |

## Data Source

Recipes and menus are Markdown files with YAML frontmatter in the Obsidian vault:

| File | Content |
|---|---|
| `Recettes/*.md` | Recipes with ingredients, steps, macros, tags |
| `Menus/*.md` | Weekly menus — the `meals:` frontmatter block is authoritative |
| `Convives.md` | Dietary profiles — constraints, allergies, aversions |
| `Presences.md` | Custody schedule, school holidays, absences |

The vault is mounted read-only on the VPS via rclone. Ingestion: `POST /api/ingest`.

## API

### Recipes
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/recipes` | List recipes (with filters) |
| GET | `/api/recipes/{slug}` | Recipe detail |
| GET | `/api/filters` | Available filter values |
| GET | `/api/recipes/{slug}/executions` | Cooking history |
| POST | `/api/recipes/{slug}/executions` | Log a cooking execution |

### Menus
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/menus` | List menus |
| POST | `/api/menus` | Create a menu |
| DELETE | `/api/menus/{slug}` | Delete a menu |
| GET | `/api/menus/{slug}/meals` | Meals for a menu |
| PATCH | `/api/menus/{slug}/meals/{id}` | Update a meal (recipe, covers) |
| GET | `/api/menus/{slug}/compatibility` | Dietary compatibility check |
| GET | `/api/menus/{slug}/shopping-list` | Generate shopping list (`?covers=N&from_date=YYYY-MM-DD`) |

### Shopping
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/shopping/import` | Import a shopping session |
| POST | `/api/shopping/persist-cart` | Persist + enrich cart items (nutrition, nutriscore, allergens) |
| GET | `/api/shopping/sessions` | List shopping sessions |
| GET | `/api/shopping/preferences` | Product preferences (blacklist, favorites) |

### Auchan Drive
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/auchan/product/{id}` | Product detail (scraped) |
| POST | `/api/auchan/remove` | Remove item from cart |

### Voice
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/audio` | Audio → STT → LLM intent → action |
| POST | `/api/intent` | Text → LLM intent → action |

### Pantry (DB-backed)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/pantry` | Pantry contents grouped by section |
| POST | `/api/pantry/items` | Add a pantry item |
| GET | `/api/pantry/items/{id}` | Item detail |
| PUT | `/api/pantry/items/{id}` | Update item (status, qty, notes) |
| DELETE | `/api/pantry/items/{id}` | Remove item |
| GET | `/api/pantry/search?q=` | Search items by name |
| PATCH | `/api/pantry` | Update pantry (legacy Markdown writer) |

### Other
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ingest` | Ingest vault into database |
| GET | `/api/stats` | Dashboard stats |
| GET | `/health` | Health check |

## MCP Servers

### Cooking Manager MCP

Local MCP server for LLM access to pantry, recipes, and menus:

```bash
python -m backend.cooking_mcp  # stdio transport
```

10 tools: `pantry_list`, `pantry_search`, `pantry_add`, `pantry_update`, `pantry_remove`, `shopping_list`, `recipe_search`, `recipe_detail`, `menu_current`, `pantry_ingest`.

### Auchan Drive MCP

Local MCP server for Auchan Drive cart management:

```bash
python -m backend.auchan_mcp  # stdio transport
```

Exposes tools: product search, cart management, and `grocery_persist_cart` (persist + enrich via the API).

## Deploy

```bash
ssh srv759970 'cd /opt/cooking-manager-2 && git pull && .venv/bin/pip install -q . && sudo systemctl restart cooking-manager'
```

## Architecture

```
cooking_manager/       # Pure domain — no network I/O
  vault.py             # Read .md files from vault
  normalizer.py        # FR frontmatter → canonical EN, slugs, dates
  ingredients.py       # Markdown body → structured ingredients + steps
  convives.py          # Dietary profiles + compatibility checks
  presence.py          # Who's at the table (custody × holidays × absences)
backend/               # FastAPI + DB schema + ingestion
  stt.py               # Voice pipeline: Deepgram STT + Groq LLM intent
  auchan.py            # Auchan Drive client (reverse-engineered)
  auchan_mcp.py        # FastMCP server (stdio) — Auchan cart
  cooking_mcp.py       # FastMCP server (stdio) — pantry, recipes, menus
web/                   # Frontend: index.html + style.css + app.js
tests/                 # Unit tests · iOS 12 compat gate · e2e (opt-in)
deploy/                # systemd unit, nginx config, install script
data/                  # Shopping sessions + photo prompt (versioned)
```

## Browser Compatibility

The frontend targets **Safari 12.5.8** (iPad mini 2 used in the kitchen). The iOS 12 compatibility gate is enforced on every commit touching `web/`. Voice features require Safari 14.5+ and are hidden on older browsers.
