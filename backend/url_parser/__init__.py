"""URL-based recipe parser — 3-tier cascade: JSON-LD → heuristic → LLM."""

from backend.url_parser.parser import parse_recipe_url, parse_recipe_html
from backend.url_parser.models import Recipe

__all__ = ["parse_recipe_url", "parse_recipe_html", "Recipe"]
