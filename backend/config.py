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

DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
DEEPGRAM_MODEL = os.environ.get("DEEPGRAM_MODEL", "nova-2")
DEEPGRAM_LANGUAGE = os.environ.get("DEEPGRAM_LANGUAGE", "fr")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "https://ollama.com")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:cloud")
