# Cooking Manager 2

Web app pour parcourir et filtrer les recettes familiales depuis le vault Obsidian.

## Stack

- **Backend** : FastAPI + asyncpg (PostgreSQL)
- **Frontend** : vanilla JS SPA
- **DB** : `postgresql-shared` (Docker) → database `cooking_manager`, user `cooking`
- **Deploy** : systemd `cooking-manager.service` + nginx sur srv759970, port 8795

## Architecture

```
cooking_manager/   # Pipeline vault → normalize → compile (CLI: build)
backend/           # FastAPI app + DB schema + ingest
  auchan.py        # Auchan Drive API client (reverse-engineered: cart, search, scraping)
  auchan_mcp.py    # FastMCP server (7 tools, stdio transport)
web/               # Frontend (index.html + style.css + app.js)
data/              # Shopping session JSON (rationale per product)
deploy/            # systemd unit + nginx conf + install script
```

## Commandes

```bash
# Build cuisine.json (legacy, standalone)
python -m cooking_manager build --vault /path/to/Cuisine

# Run web server
python -m cooking_manager serve --port 8795

# Deploy on VPS
ssh srv759970 'cd /opt/cooking-manager-2 && bash deploy/install.sh'
```

## Vault source

Le vault Obsidian `Noyau/Cuisine/` est dans Dropbox, monté en lecture sur le VPS via rclone (`/mnt/dropbox-full/JULIEN/Obsidian/vault/Noyau/Cuisine`). L'ingestion est déclenchée via `POST /api/ingest`.

## Auchan Drive API

Client reverse-engineered (`backend/auchan.py`). Auth : Bearer JWT Keycloak + `x-gravitee-api-key`. Catalogue : SSR scraping (pas d'API produit). Cart : `POST api.auchan.fr/checkout/v1/carts/{cartId}/items` (add/update/remove via `desiredQuantity`). Remove nécessite l'`id` interne (GET cart d'abord). MCP local : `python -m backend.auchan_mcp` (stdio).

## Gotchas

- Le token Auchan expire fréquemment — refresh via navigateur uniquement
- `consentId` requis comme query param sur tous les appels cart
- La recherche SSR nécessite le cookie `auchan_store_reference=874` (Aubagne)
- Remove cart : l'`id` interne (UUID) ≠ `productId` — toujours GET cart d'abord

## Lint gate

```bash
python -m ruff check cooking_manager/ backend/
python -m pyright
```
