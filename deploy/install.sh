#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/cooking-manager-2"
DB_USER="cooking"
DB_NAME="cooking_manager"
DB_PASS="cooking"

echo "=== Cooking Manager — Install ==="

# 1. Create PostgreSQL user and database (via docker exec)
echo "[1/6] Database setup…"
docker exec postgresql-shared psql -U postgres -tc \
  "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 || \
  docker exec postgresql-shared psql -U postgres -c \
  "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}'"

docker exec postgresql-shared psql -U postgres -tc \
  "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
  docker exec postgresql-shared psql -U postgres -c \
  "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}"

docker exec postgresql-shared psql -U postgres -c \
  "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER}"

# 2. Sync code
echo "[2/6] Syncing code…"
sudo mkdir -p "${APP_DIR}"
sudo chown automation:automation "${APP_DIR}"
rsync -a --delete --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
  "$(dirname "$0")/../" "${APP_DIR}/"

# 3. Python venv
echo "[3/6] Python environment…"
cd "${APP_DIR}"
python3 -m venv .venv 2>/dev/null || true
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q .

# 4. Systemd service
echo "[4/6] Systemd service…"
sudo cp deploy/cooking-manager.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable cooking-manager
sudo systemctl restart cooking-manager

# 5. Nginx
echo "[5/6] Nginx config…"
sudo cp deploy/cooking-manager.nginx.conf /etc/nginx/sites-available/cooking-manager
sudo ln -sf /etc/nginx/sites-available/cooking-manager /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 6. Initial ingest
echo "[6/6] Initial ingest…"
sleep 2
curl -s -X POST http://127.0.0.1:8795/api/ingest | python3 -m json.tool

echo ""
echo "=== Done. Health check: ==="
curl -s http://127.0.0.1:8795/health | python3 -m json.tool
echo "INSTALL_COMPLETE"
