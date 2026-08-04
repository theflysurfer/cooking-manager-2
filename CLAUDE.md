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

# Deploy on VPS — /opt/cooking-manager-2 est un vrai clone git (depuis 2026-08-04)
ssh srv759970 'cd /opt/cooking-manager-2 && git pull && .venv/bin/pip install -q . && sudo systemctl restart cooking-manager'
```

## Vault source

Le vault Obsidian `Noyau/Cuisine/` est dans Dropbox, monté en lecture sur le VPS via rclone (`/mnt/dropbox-full/JULIEN/Obsidian/vault/Noyau/Cuisine`). L'ingestion est déclenchée via `POST /api/ingest`.

## Auchan Drive API

Client reverse-engineered (`backend/auchan.py`). Auth : Bearer JWT Keycloak + `x-gravitee-api-key`. Catalogue : SSR scraping (pas d'API produit). Cart : `POST api.auchan.fr/checkout/v1/carts/{cartId}/items` (add/update/remove via `desiredQuantity`). Remove nécessite l'`id` interne (GET cart d'abord). MCP local : `python -m backend.auchan_mcp` (stdio) — expose aussi `grocery_persist_cart`, qui persiste et enrichit un panier via `POST /api/shopping/persist-cart`.

⚠️ Le connecteur **claude.ai** `Auchan Drive` (hébergé, pas ce repo) n'expose que l'ajout au panier — `quantity=0` pour supprimer y échoue systématiquement en 500 (refs #13). Toute suppression/mise à jour de quantité doit passer par `backend/auchan_mcp.py` ou un appel direct à `AuchanClient`.

## Persistance + enrichissement nutritionnel

`POST /api/shopping/persist-cart` persiste chaque article dans `shopping_product` et l'enrichit en direct (nutrition, nutriscore, ingrédients, allergènes, caractéristiques, photo, prix/kg) via `backend/auchan.py::find_product_detail()` — pont entre l'UUID interne du panier et l'ID public catalogue (recherche par nom, puis scrape de la fiche produit). Séquentiel, un item peut prendre plusieurs secondes — le timeout nginx `/api/` est à 300s pour cette raison (`deploy/cooking-manager.nginx.conf`).

## Gotchas

- Le token Auchan expire fréquemment — refresh via navigateur uniquement
- `consentId` requis comme query param sur tous les appels cart
- La recherche SSR nécessite le cookie `auchan_store_reference=874` (Aubagne)
- Remove cart : l'`id` interne (UUID) ≠ `productId` — toujours GET cart d'abord
- `httpx`/`selectolax`/`mcp` sont des dépendances déclarées dans `pyproject.toml` — un venv reconstruit à neuf (`pip install .`) est le test de vérité si ce fichier dérive

## Lint gate

```bash
python -m ruff check cooking_manager/ backend/
python -m pyright
```
