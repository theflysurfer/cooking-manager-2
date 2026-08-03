"""Read recipe, menu, convives, and garde-manger files from the Obsidian vault."""

import re
from pathlib import Path

import yaml


def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text) from a Markdown file with YAML front matter."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\A---\n(.*?\n)---\n?(.*)", text, re.DOTALL)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, m.group(2)


def read_recipes(vault_root: Path) -> list[dict]:
    """Read all recipe .md files under Cuisine/Recettes/."""
    recipes_dir = vault_root / "Recettes"
    if not recipes_dir.is_dir():
        return []
    results = []
    for p in sorted(recipes_dir.glob("*.md")):
        if p.name.startswith("_"):
            continue
        fm, body = _parse_frontmatter(p)
        if not fm.get("title"):
            continue
        fm["_source_path"] = str(p)
        fm["_body"] = body
        fm["_mtime"] = p.stat().st_mtime
        results.append(fm)
    return results


def read_menus(vault_root: Path) -> list[dict]:
    """Read all menu .md files under Cuisine/Menus/."""
    menus_dir = vault_root / "Menus"
    if not menus_dir.is_dir():
        return []
    results = []
    for p in sorted(menus_dir.glob("*.md")):
        if p.name.startswith("_"):
            continue
        fm, body = _parse_frontmatter(p)
        if not fm.get("title"):
            continue
        fm["_source_path"] = str(p)
        fm["_body"] = body
        fm["_mtime"] = p.stat().st_mtime
        results.append(fm)
    return results


def read_convives(vault_root: Path) -> dict:
    """Read Convives.md — returns raw frontmatter + body."""
    p = vault_root / "Convives.md"
    if not p.exists():
        return {}
    fm, body = _parse_frontmatter(p)
    fm["_body"] = body
    return fm


def read_garde_manger(vault_root: Path) -> dict:
    """Read Garde-manger.md — returns raw frontmatter + body."""
    p = vault_root / "Garde-manger.md"
    if not p.exists():
        return {}
    fm, body = _parse_frontmatter(p)
    fm["_body"] = body
    return fm
