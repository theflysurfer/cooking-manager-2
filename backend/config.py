"""App configuration from environment variables."""

import os

DATABASE_DSN = os.environ.get(
    "DATABASE_URL",
    "postgresql://cooking:cooking@127.0.0.1:5432/cooking_manager",
)

VAULT_ROOT = os.environ.get(
    "VAULT_ROOT",
    "/mnt/dropbox-full/JULIEN/Obsidian/vault/Noyau/Cuisine",
)

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8795"))
