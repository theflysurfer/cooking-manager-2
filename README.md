# Cooking Manager 2

Web app to browse and filter family recipes from the Obsidian vault.

## Stack

- **Backend**: FastAPI + asyncpg (PostgreSQL)
- **Frontend**: vanilla JS SPA (no framework)
- **Database**: PostgreSQL via `postgresql-shared` Docker container
- **Deploy**: systemd + nginx on VPS, port 8795

## Usage

```bash
# Run locally
python -m cooking_manager serve --port 8795

# Ingest recipes from vault
curl -X POST http://localhost:8795/api/ingest

# Build cuisine.json (legacy CLI)
python -m cooking_manager build --vault /path/to/Cuisine
```

## Data Source

Recipes and menus are Markdown files with YAML frontmatter in the Obsidian vault (`Noyau/Cuisine/Recettes/` and `Noyau/Cuisine/Menus/`). The vault is mounted read-only on the VPS via rclone. Ingestion is triggered via `POST /api/ingest`.

## Auchan Drive Integration

Reverse-engineered API client for Auchan Drive grocery shopping. Search products, view nutrition/ingredients, manage cart (add/remove/update). Also available as a local MCP server:

```bash
python -m backend.auchan_mcp  # stdio transport — 7 tools
```

Requires `AUCHAN_TOKEN` (Bearer JWT from browser) and `AUCHAN_CART_ID` env vars for cart operations.

## Deploy

```bash
ssh srv759970 'cd /opt/cooking-manager-2 && bash deploy/install.sh'
```

Live at: `https://cooking.srv759970.hstgr.cloud`
