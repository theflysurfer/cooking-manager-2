from __future__ import annotations

import httpx

_CF_MARKERS = [
    "Checking if the site connection is secure",
    "cf-challenge",
    "Just a moment...",
    "_cf_chl",
]


def _looks_like_cf_block(html: str, status: int) -> bool:
    if status in (403, 503):
        return True
    return any(marker in html for marker in _CF_MARKERS)


async def fetch_html(
    url: str,
    *,
    timeout: float = 15.0,
    flaresolverr_url: str | None = None,
) -> str | None:
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (compatible; RecipeParser/0.1)"},
    ) as client:
        try:
            resp = await client.get(url)
        except httpx.HTTPError:
            return None

        if not _looks_like_cf_block(resp.text, resp.status_code):
            return resp.text

        if not flaresolverr_url:
            return resp.text if resp.status_code == 200 else None

        try:
            cf_resp = await client.post(
                flaresolverr_url,
                json={"cmd": "request.get", "url": url, "maxTimeout": 30000},
                timeout=45.0,
            )
            data = cf_resp.json()
            solution = data.get("solution", {})
            return solution.get("response") or resp.text
        except Exception:
            return resp.text if resp.status_code == 200 else None
