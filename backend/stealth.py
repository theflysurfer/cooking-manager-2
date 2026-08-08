"""Thin HTTP client for the stealth-fetch service (port 8410).

All HTML fetching with anti-bot bypass goes through stealth-fetch.
Proxy management, TLS fingerprinting, and engine escalation are
stealth-fetch's responsibility — consumers just send {url, cookies}.
"""

import logging
import os

import httpx

log = logging.getLogger(__name__)

STEALTH_URL = os.environ.get(
    "STEALTH_FETCH_URL", "http://127.0.0.1:8410"
)


async def fetch_html(
    url: str,
    *,
    cookies: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    max_level: int = 3,
) -> str:
    """Fetch HTML via stealth-fetch HTTP API. Raises on failure."""
    payload: dict = {"url": url, "max_level": max_level, "timeout": timeout}
    if cookies:
        payload["cookies"] = cookies
    if headers:
        payload["headers"] = headers

    async with httpx.AsyncClient(timeout=timeout + 10) as client:
        r = await client.post(f"{STEALTH_URL}/fetch-html", json=payload)
        r.raise_for_status()

    data = r.json()
    engine = data.get("engine", "?")
    elapsed = data.get("elapsed_ms", 0)
    log.info("stealth-fetch: %s via %s (%d ms)", url[:80], engine, elapsed)
    return data["html"]
