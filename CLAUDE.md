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
web/               # Frontend (index.html + style.css + app.js)
deploy/            # systemd unit + nginx conf + install script
```

## Commandes

```bash
# Build cuisine.json (legacy, standalone)
python -m cooking_manager build --vault /path/to/Cuisine

# Run web server
python -m cooking_manager serve --port 8795

# Deploy on VPS
ssh srv759970 'cd /opt/cooking-manager && bash deploy/install.sh'
```

## Vault source

Le vault Obsidian `Cuisine/` est dans Dropbox, monté en lecture sur le VPS via rclone (`/mnt/dropbox-full/JULIEN/Obsidian/vault/Cuisine`). L'ingestion est déclenchée via `POST /api/ingest`.

## Lint gate

```bash
python -m ruff check cooking_manager/ backend/
python -m pyright
```
