"""Compile normalized recipes + menus into the cuisine.json artifact."""

import json
from datetime import date, datetime

SCHEMA_VERSION = "cuisine/1"


def compile_artifact(
    recipes: list[dict],
    menus: list[dict],
    convives: dict | None = None,
    warnings: list[str] | None = None,
) -> dict:
    """Build the final cuisine.json structure."""
    # Strip internal fields from output
    clean_recipes = [_strip_internal(r) for r in recipes]
    clean_menus = [_strip_internal(m) for m in menus]

    return {
        "schema": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "recipes": clean_recipes,
        "menus": clean_menus,
        "convives": _strip_internal(convives) if convives else None,
        "counts": {
            "recipes": len(clean_recipes),
            "menus": len(clean_menus),
        },
        "warnings": warnings or [],
    }


def _strip_internal(d: dict) -> dict:
    """Remove keys starting with _ (internal metadata)."""
    return {k: v for k, v in d.items() if not k.startswith("_")}


class _DateEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        return super().default(o)


def to_json(artifact: dict) -> str:
    return json.dumps(artifact, ensure_ascii=False, indent=2, cls=_DateEncoder)
