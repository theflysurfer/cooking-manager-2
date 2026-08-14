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


def _declared_date(fm: dict) -> str:
    """Date que le fichier DÉCLARE — jamais son mtime.

    ⚠️ Le mtime ne peut pas servir à départager deux fiches : sur le VPS, le
    vault est un mount rclone, donc le mtime date la COPIE, pas la donnée. Deux
    fichiers transférés le même jour y sont indiscernables, et le plus récent
    des deux peut porter le mtime le plus ancien.
    """
    return str(fm.get("updated") or fm.get("created") or "")


def read_recipes(vault_root: Path) -> list[dict]:
    """Read all recipe .md files under Cuisine/Recettes/.

    Deux fichiers peuvent déclarer le MÊME `slug` — le slug est la clé, pas le
    nom de fichier. L'upsert d'ingestion n'en garde alors qu'un, et lequel
    dépendait de l'ordre alphabétique du glob : `<slug>-v2.md` étant lu AVANT
    `<slug>.md`, c'est la version périmée qui écrasait la bonne. Silencieusement,
    et à rebours de l'intention (constaté sur le journal Creami : la prod servait
    l'état du 08/07 alors que le vault décrivait celui du 06/08).

    On tranche donc sur la date DÉCLARÉE, et on garde trace du perdant pour que
    l'ingestion puisse le dire.
    """
    recipes_dir = vault_root / "Recettes"
    if not recipes_dir.is_dir():
        return []
    by_slug: dict[str, dict] = {}
    results: list[dict] = []
    for p in sorted(recipes_dir.glob("*.md")):
        if p.name.startswith("_"):
            continue
        fm, body = _parse_frontmatter(p)
        if not fm.get("title"):
            continue
        fm["_source_path"] = str(p)
        fm["_body"] = body
        fm["_mtime"] = p.stat().st_mtime

        slug = str(fm.get("slug") or "")
        if not slug:
            results.append(fm)
            continue

        previous = by_slug.get(slug)
        if previous is None:
            by_slug[slug] = fm
            results.append(fm)
            continue

        # Collision : le plus récemment déclaré gagne, à égalité le premier lu.
        loser, winner = (
            (previous, fm)
            if _declared_date(fm) > _declared_date(previous)
            else (fm, previous)
        )
        winner.setdefault("_duplicate_paths", []).append(loser["_source_path"])
        winner["_duplicate_paths"] += loser.pop("_duplicate_paths", [])
        if winner is fm:
            results[results.index(previous)] = fm
            by_slug[slug] = fm
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
