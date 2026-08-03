"""Orchestrate the build pipeline: read → normalize → compile → write."""

import json
from pathlib import Path

from .vault import read_recipes, read_menus, read_convives
from .normalizer import normalize_recipe, normalize_menu
from .compiler import compile_artifact, to_json


def build(vault_root: Path, output: Path) -> dict:
    """Run the full pipeline and write cuisine.json. Returns the artifact."""
    warnings: list[str] = []

    raw_recipes = read_recipes(vault_root)
    recipes = []
    for raw in raw_recipes:
        normalized, warns = normalize_recipe(raw)
        warnings.extend(warns)
        recipes.append(normalized)

    raw_menus = read_menus(vault_root)
    menus = []
    for raw in raw_menus:
        normalized, warns = normalize_menu(raw)
        warnings.extend(warns)
        menus.append(normalized)

    convives = read_convives(vault_root)

    artifact = compile_artifact(recipes, menus, convives, warnings)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(to_json(artifact), encoding="utf-8")

    return artifact
