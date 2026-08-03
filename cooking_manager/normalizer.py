"""Deterministic normalizer for recipe and menu frontmatter.

Fixes common coach errors: French→English key aliases, type coercions,
value normalization. No LLM — pure dict transforms.
"""

import re
from datetime import datetime

# ── Key aliases (FR coach → EN canonical) ────────────────────────────

RECIPE_KEY_ALIASES: dict[str, str] = {
    # time
    "duree_total_min": "total_time_min",
    "duree_totale_min": "total_time_min",
    "temps_total": "total_time_min",
    "temps_total_min": "total_time_min",
    "temps_preparation": "prep_time_min",
    "temps_prep": "prep_time_min",
    "prep": "prep_time_min",
    "temps_cuisson": "cook_time_min",
    "cuisson": "cook_time_min",
    # servings
    "portions_base": "servings",
    "portions": "servings",
    "couverts": "servings",
    "nb_portions": "servings",
    # identity
    "statut": "status",
    "famille": "family",
    "regime": "family",
    "type": "recipe_type",
    # nutrition
    "macros_per_portion_julien": "macros",
    "macros_per_portion": "macros",
    "macros_portion": "macros",
    # constraints
    "contraintes_compatibles": "compatible_constraints",
    "contraintes": "compatible_constraints",
    # media
    "photo": "photo_url",
    "image": "photo_url",
    "image_url": "photo_url",
    # content
    "ingredients": "ingredients",
    "ingrédients": "ingredients",
    "etapes": "steps",
    "étapes": "steps",
    # misc
    "apprecie_par": "appreciated_by",
    "substitutions_appliquees": "applied_substitutions",
    "regime_construction": "construction_regime",
    "mediterranean_criteria_covered": "mediterranean_criteria",
    "executions": "execution_count",
    "recettes_liees": "linked_recipes",
}

MENU_KEY_ALIASES: dict[str, str] = {
    "semaine_debut": "week_start",
    "semaine_fin": "week_end",
    "statut": "status",
    "recettes_liees": "linked_recipes",
}

# ── Status normalization ─────────────────────────────────────────────

STATUS_ALIASES: dict[str, str] = {
    "piste": "draft",
    "a-tester": "to_test",
    "à-tester": "to_test",
    "a_tester": "to_test",
    "validee": "validated",
    "validée": "validated",
    "en-rotation": "in_rotation",
    "en_rotation": "in_rotation",
    "propose": "proposed",
    "proposé": "proposed",
    "proposée": "proposed",
    "actif": "active",
    "archive": "archived",
    "archivé": "archived",
    "archivée": "archived",
}

# ── Macros key normalization ─────────────────────────────────────────

MACROS_KEY_ALIASES: dict[str, str] = {
    "prot": "protein",
    "protéines": "protein",
    "proteines": "protein",
    "P": "protein",
    "gluc": "carbs",
    "glucides": "carbs",
    "G": "carbs",
    "lip": "fat",
    "lipides": "fat",
    "L": "fat",
}


def _apply_key_aliases(data: dict, aliases: dict[str, str]) -> dict:
    """Rename keys using alias map. Original key kept if no alias."""
    out: dict = {}
    for k, v in data.items():
        canonical = aliases.get(k, k)
        if canonical not in out:
            out[canonical] = v
    return out


def _coerce_minutes(value) -> int | None:
    """Coerce '20 min', '20min', '1h30', 60, '60' to int minutes."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if not isinstance(value, str):
        return None
    s = value.strip().lower()
    # "1h30" or "1h 30"
    m = re.match(r"(\d+)\s*h\s*(\d*)", s)
    if m:
        hours = int(m.group(1))
        mins = int(m.group(2)) if m.group(2) else 0
        return hours * 60 + mins
    # "20 min" or "20min" or just "20"
    m = re.match(r"(\d+)\s*(?:min(?:utes?)?)?$", s)
    if m:
        return int(m.group(1))
    return None


def _coerce_int(value) -> int | None:
    """Coerce '4 personnes', '4', 4 to int."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if not isinstance(value, str):
        return None
    m = re.match(r"(\d+)", value.strip())
    return int(m.group(1)) if m else None


def _coerce_list(value) -> list:
    """Coerce 'a, b, c' string to ['a', 'b', 'c']. Pass through lists."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return []


def _normalize_macros(macros) -> dict | None:
    """Normalize macros dict keys and ensure numeric values."""
    if not isinstance(macros, dict):
        return None
    out = {}
    for k, v in macros.items():
        canonical = MACROS_KEY_ALIASES.get(k, k)
        out[canonical] = _coerce_int(v) if not isinstance(v, (int, float)) else v
    return out


def _ensure_dates(data: dict) -> None:
    """Fill created/updated from _mtime if missing."""
    mtime = data.get("_mtime")
    if mtime and not data.get("created"):
        data["created"] = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    if mtime and not data.get("updated"):
        data["updated"] = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    # Normalize date objects to strings
    for key in ("created", "updated"):
        val = data.get(key)
        if val is not None and hasattr(val, "isoformat"):
            data[key] = val.isoformat()


def _compute_protein_density(macros: dict | None) -> float | None:
    """gP/kcal ratio. None if data missing."""
    if not macros:
        return None
    kcal = macros.get("kcal")
    protein = macros.get("protein")
    if not kcal or not protein:
        return None
    try:
        return round(float(protein) / float(kcal), 3)
    except (ValueError, ZeroDivisionError):
        return None


def normalize_recipe(raw: dict) -> tuple[dict, list[str]]:
    """Normalize a raw recipe frontmatter dict.

    Returns (normalized_dict, list_of_warnings).
    """
    warnings: list[str] = []
    slug = raw.get("slug", "")

    data = _apply_key_aliases(raw, RECIPE_KEY_ALIASES)

    # Ensure slug from filename if missing
    if not data.get("slug"):
        src = data.get("_source_path", "")
        if src:
            from pathlib import Path
            data["slug"] = Path(src).stem

    # Time fields
    for field in ("total_time_min", "prep_time_min", "cook_time_min"):
        if field in data:
            coerced = _coerce_minutes(data[field])
            if coerced is not None:
                data[field] = coerced
            else:
                warnings.append(f"{slug}: cannot coerce {field}={data[field]!r} to minutes")

    # Servings
    if "servings" in data:
        coerced = _coerce_int(data["servings"])
        if coerced is not None:
            data["servings"] = coerced
        else:
            warnings.append(f"{slug}: cannot coerce servings={data['servings']!r}")

    # Status
    if "status" in data:
        raw_status = str(data["status"]).strip().lower()
        data["status"] = STATUS_ALIASES.get(raw_status, raw_status)

    # List fields
    for field in ("tags", "compatible_constraints", "sources", "appreciated_by",
                   "applied_substitutions", "ingredients", "steps", "linked_recipes",
                   "mediterranean_criteria"):
        if field in data:
            data[field] = _coerce_list(data[field])

    # Macros
    if "macros" in data:
        data["macros"] = _normalize_macros(data["macros"])

    # Protein density
    if "macros" in data and data["macros"]:
        density = _compute_protein_density(data["macros"])
        if density is not None:
            data["protein_density"] = density

    # Dates
    _ensure_dates(data)

    return data, warnings


def normalize_menu(raw: dict) -> tuple[dict, list[str]]:
    """Normalize a raw menu frontmatter dict.

    Returns (normalized_dict, list_of_warnings).
    """
    warnings: list[str] = []

    data = _apply_key_aliases(raw, MENU_KEY_ALIASES)

    # Status
    if "status" in data:
        raw_status = str(data["status"]).strip().lower()
        data["status"] = STATUS_ALIASES.get(raw_status, raw_status)

    # List fields
    for field in ("linked_recipes",):
        if field in data:
            data[field] = _coerce_list(data[field])

    # Dates
    _ensure_dates(data)

    return data, warnings
