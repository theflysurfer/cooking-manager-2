from __future__ import annotations

import asyncio

from selectolax.parser import HTMLParser

from backend.url_parser.fetcher import fetch_html
from backend.url_parser.heuristic import extract_from_html
from backend.url_parser.jsonld import extract_from_jsonld
from backend.url_parser.llm import extract_with_llm
from backend.url_parser.models import Recipe


def parse_recipe_html(
    html: str,
    url: str | None = None,
    *,
    enable_llm: bool = False,
    ollama_host: str = "https://ollama.com",
    llm_model: str = "gemma3:cloud",
) -> Recipe | None:
    recipe = extract_from_jsonld(html, url)
    if recipe and recipe.ingredients:
        return recipe

    recipe = extract_from_html(html, url)
    if recipe and recipe.ingredients:
        return recipe

    if not enable_llm:
        return recipe

    tree = HTMLParser(html)
    text = tree.body.text(separator="\n") if tree.body else html[:8000]
    return extract_with_llm(
        text, url, ollama_host=ollama_host, model=llm_model
    )


async def parse_recipe_url(
    url: str,
    *,
    enable_llm: bool = False,
    ollama_host: str = "https://ollama.com",
    llm_model: str = "gemma3:cloud",
    flaresolverr_url: str | None = None,
    fetch_timeout: float = 15.0,
) -> Recipe | None:
    html = await fetch_html(url, timeout=fetch_timeout, flaresolverr_url=flaresolverr_url)
    if not html:
        return None

    return await asyncio.to_thread(
        parse_recipe_html,
        html,
        url,
        enable_llm=enable_llm,
        ollama_host=ollama_host,
        llm_model=llm_model,
    )
