#!/bin/bash
# Read Deepgram and Ollama keys from systemd credstore, then exec the app.
# credentials are loaded via LoadCredentialEncrypted in the unit file.

if [ -n "$CREDENTIALS_DIRECTORY" ]; then
  [ -f "$CREDENTIALS_DIRECTORY/cooking-deepgram-key" ] && \
    export DEEPGRAM_API_KEY=$(cat "$CREDENTIALS_DIRECTORY/cooking-deepgram-key")
  [ -f "$CREDENTIALS_DIRECTORY/cooking-ollama-key" ] && \
    export OLLAMA_API_KEY=$(cat "$CREDENTIALS_DIRECTORY/cooking-ollama-key")
fi

exec /opt/cooking-manager-2/.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8795
