"""Macros d'une recette, calculées depuis ses ingrédients."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .ingredients import _singular, normalize_name

GRAMS_PER_UNIT: dict[str, float] = {
    "g": 1.0,
    "kg": 1000.0,
    "ml": 1.0,
    "cl": 10.0,
    "l": 1000.0,
    "c.s.": 15.0,
    "c.c.": 5.0,
}

UNCONVERTIBLE_REASON = "unité non convertible en grammes sans poids unitaire"

@dataclass
class Macros:
    """Valeurs pour 100 g. `None` = non renseigné, jamais 0 par défaut."""

    kcal: float | None = None
    protein: float | None = None
    carbs: float | None = None
    fat: float | None = None

    def complete(self) -> bool:
        return None not in (self.kcal, self.protein, self.carbs, self.fat)

@dataclass
class FoodEntry:
    key: str
    title: str
    forms: dict[str, Macros]
    source: str
    kind: str
    statut: str = ""
    path: str = ""

    @property
    def rank(self) -> int:
        """Préséance : plus petit = plus fiable."""
        return {"marque": 1, "drive": 2, "generique": 3}.get(self.kind, 4)

    def macros_for(self, ingredient_name: str) -> tuple[Macros | None, str]:
        """Macros de la forme demandée, ou (None, motif) si on ne peut trancher."""
        if len(self.forms) == 1:
            return next(iter(self.forms.values())), ""
        if not self.forms:
            return None, "fiche sans tableau /100 g"

        name = normalize_name(ingredient_name)
        for label, macros in self.forms.items():
            words = [w for w in label.replace("/", " ").split() if w]
            if any(w in FORM_WORDS and re.search(rf"\b{re.escape(_singular(w))}\b", name)
                   for w in words):
                return macros, ""
        return None, f"forme ambiguë ({' / '.join(self.forms)}) — préciser dans la recette"

@dataclass
class ResolvedIngredient:
    name: str
    grams: float | None
    entry: FoodEntry | None
    reason: str = ""

    @property
    def resolved(self) -> bool:
        return self.grams is not None and self.entry is not None

@dataclass
class RecipeMacros:
    kcal: float = 0.0
    protein: float = 0.0
    carbs: float = 0.0
    fat: float = 0.0
    resolved: list[ResolvedIngredient] = field(default_factory=list)
    unresolved: list[ResolvedIngredient] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        """Part des ingrédients réellement pris en compte."""
        total = len(self.resolved) + len(self.unresolved)
        return len(self.resolved) / total if total else 0.0

def reconcile(kcal: float | None, protein: float | None,
              carbs: float | None, fat: float | None) -> dict:
    """Confronte les kcal annoncées à la somme des macros (Règle 2bis)."""
    if kcal is None or protein is None or carbs is None or fat is None or not kcal:
        return {"reconciled": None, "reason": "données incomplètes"}
    rebuilt = protein * 4 + carbs * 4 + fat * 9
    gap = abs(kcal - rebuilt) / kcal
    return {
        "reconciled": gap <= 0.05,
        "kcal_declared": round(kcal, 1),
        "kcal_rebuilt": round(rebuilt, 1),
        "gap_pct": round(gap * 100, 1),
    }

_FM_RE = re.compile(r"\A---\n(.*?)\n---", re.DOTALL)
_NUM_RE = re.compile(r"(\d+(?:[.,]\d+)?)")
_PER_100G_RE = re.compile(r"/\s*100\s*(?:g|ml)", re.IGNORECASE)

_METRIC_KEYS = {
    "energie": "kcal", "énergie": "kcal", "calories": "kcal", "kcal": "kcal",
    "proteines": "protein", "protéines": "protein", "p": "protein",
    "glucides": "carbs", "g": "carbs",
    "lipides": "fat", "l": "fat",
}

_PARTICLES = frozenset({"de", "du", "des", "d", "l", "la", "le", "les",
                        "a", "au", "aux", "en"})

def match_key(name: str) -> str:
    """Clé d'appariement : nom normalisé, débarrassé des particules."""
    return " ".join(w for w in normalize_name(name).split() if w not in _PARTICLES)

FORM_WORDS = ("cuit", "cuite", "cuits", "cuites", "cru", "crue", "crus", "crues",
              "sec", "secs", "seche", "sechees", "egoutte", "egouttes")

def _first_number(text: str) -> float | None:
    m = _NUM_RE.search(text.replace("~", ""))
    return float(m.group(1).replace(",", ".")) if m else None

KJ_PER_KCAL = 4.184

MAX_KCAL_PER_100G = 950.0

_KCAL_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*kcal", re.IGNORECASE)
_KJ_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*kj", re.IGNORECASE)


def read_energy(text: str) -> float | None:
    """Une énergie en kcal : la cellule dit son unité, on ne lit pas le premier nombre venu."""
    clean = text.replace("~", "")
    m = _KCAL_RE.search(clean)
    if m:
        return float(m.group(1).replace(",", "."))
    m = _KJ_RE.search(clean)
    if m:
        return round(float(m.group(1).replace(",", ".")) / KJ_PER_KCAL, 1)
    value = _first_number(clean)
    if value is not None and value > MAX_KCAL_PER_100G:
        return None
    return value

def _cells(line: str) -> list[str]:
    return [c.strip().strip("*").strip() for c in line.strip().strip("|").split("|")]

def parse_food_sheet(text: str) -> tuple[dict, dict[str, Macros]]:
    """Fiche markdown → (frontmatter, {forme: macros pour 100 g})."""
    fm: dict = {}
    m = _FM_RE.match(text)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip().strip('"')

    _PER_100G_IN_TEXT = bool(re.search(r"pour\s*100\s*(?:g|ml)", text, re.IGNORECASE))

    forms: dict[str, Macros] = {}
    columns: dict[int, str] = {}
    metric_cols: dict[int, str] = {}
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = _cells(line)

        if not columns and not metric_cols:
            found = {
                i: _PER_100G_RE.sub("", c).strip().lower() or "100g"
                for i, c in enumerate(cells) if _PER_100G_RE.search(c)
            }
            if found:
                columns = found
                forms = {label: Macros() for label in columns.values()}
                continue
            metrics = {i: _METRIC_KEYS[c.lower()]
                       for i, c in enumerate(cells) if c.lower() in _METRIC_KEYS}
            if len(metrics) >= 3:
                metric_cols = metrics
                continue
            if len(cells) == 2 and _PER_100G_IN_TEXT:
                columns = {1: "100g"}
                forms = {"100g": Macros()}
            continue

        if metric_cols:
            label = cells[0].strip().lower()
            if not label or set(label) <= {"-", " "}:
                continue
            macros = forms.setdefault(label, Macros())
            for idx, key in metric_cols.items():
                if idx < len(cells) and getattr(macros, key) is None:
                    read = read_energy if key == "kcal" else _first_number
                    setattr(macros, key, read(cells[idx]))
            continue

        key = _METRIC_KEYS.get(cells[0].lower())
        if not key:
            continue
        read = read_energy if key == "kcal" else _first_number
        for idx, label in columns.items():
            if idx < len(cells) and getattr(forms[label], key) is None:
                setattr(forms[label], key, read(cells[idx]))

    return fm, forms

_BASE_CACHE: dict[str, dict[str, FoodEntry]] = {}

def load_food_base_cached(root: Path) -> dict[str, FoodEntry]:
    """`load_food_base` mémoïsé."""
    key = str(root)
    if key not in _BASE_CACHE:
        _BASE_CACHE[key] = load_food_base(root)
    return _BASE_CACHE[key]

def reset_food_cache() -> None:
    _BASE_CACHE.clear()

def load_food_base(root: Path) -> dict[str, FoodEntry]:
    """Charge `aliments-vérifiés/` → index par nom normalisé."""
    index: dict[str, FoodEntry] = {}
    if not root.is_dir():
        return index

    for path in sorted(root.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        try:
            fm, forms = parse_food_sheet(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if not any(m.kcal is not None or m.protein is not None for m in forms.values()):
            continue

        title = path.stem.replace("-", " ")
        entry = FoodEntry(
            key=match_key(title),
            title=title,
            forms=forms,
            source=fm.get("source", ""),
            kind=fm.get("type", "generique"),
            statut=fm.get("statut", ""),
            path=str(path),
        )
        current = index.get(entry.key)
        if current is None or entry.rank < current.rank:
            index[entry.key] = entry
    return index

_DRIVE_KEYS = {
    "valeur énergétique (kcal)": "kcal", "valeur energetique (kcal)": "kcal",
    "énergie (kcal)": "kcal", "kcal": "kcal",
    "protéines": "protein", "proteines": "protein",
    "glucides": "carbs",
    "matières grasses": "fat", "matieres grasses": "fat", "lipides": "fat",
}

def entry_from_product(name: str, nutrition: dict) -> FoodEntry | None:
    """Ligne `shopping_product` → fiche aliment, ou None si inexploitable."""
    if not name or not isinstance(nutrition, dict):
        return None
    macros = Macros()
    for raw_key, raw_value in nutrition.items():
        key = _DRIVE_KEYS.get(str(raw_key).strip().lower())
        if key and getattr(macros, key) is None:
            setattr(macros, key, _first_number(str(raw_value)))
    if macros.kcal is None and macros.protein is None:
        return None
    return FoodEntry(key=match_key(name), title=name, forms={"100g": macros},
                     source="drive", kind="drive")

def merge_sources(*bases: dict[str, FoodEntry]) -> dict[str, FoodEntry]:
    """Fusionne plusieurs bases en respectant la préséance (marque < drive < générique)."""
    merged: dict[str, FoodEntry] = {}
    for base in bases:
        for key, entry in base.items():
            current = merged.get(key)
            if current is None or entry.rank < current.rank:
                merged[key] = entry
    return merged

def match_entry(name_normalized: str, base: dict[str, FoodEntry]) -> FoodEntry | None:
    """Ingrédient → fiche. Exact d'abord, puis le préfixe le plus long."""
    name = match_key(name_normalized)
    if not name:
        return None
    if name in base:
        return base[name]

    best: FoodEntry | None = None
    for key, entry in base.items():
        if name.startswith(key + " ") or key == name:
            if best is None or len(key) > len(best.key):
                best = entry
    return best

def to_grams(qty, unit: str | None) -> float | None:
    """Quantité + unité → grammes, ou None si l'unité n'est pas convertible."""
    if qty is None:
        return None
    factor = GRAMS_PER_UNIT.get((unit or "").lower())
    return float(qty) * factor if factor is not None else None

def recipe_macros(ingredients: list, base: dict[str, FoodEntry]) -> RecipeMacros:
    """Ingrédients parsés + base aliments → macros totales et couverture."""
    out = RecipeMacros()

    for ing in ingredients:
        get = ing.get if isinstance(ing, dict) else lambda k, o=ing: getattr(o, k, None)
        name = str(get("name_normalized") or get("name") or "")
        label = str(get("raw") or get("name") or name)

        if get("is_optional"):
            continue

        grams = to_grams(get("qty_min"), get("unit"))
        entry = match_entry(name, base)

        if grams is None:
            out.unresolved.append(ResolvedIngredient(label, None, entry,
                                                     UNCONVERTIBLE_REASON))
            continue
        if entry is None:
            out.unresolved.append(ResolvedIngredient(label, grams, None,
                                                     "aucune fiche aliment"))
            continue

        macros, why = entry.macros_for(label)
        if macros is None:
            out.unresolved.append(ResolvedIngredient(label, grams, entry, why))
            continue

        ratio = grams / 100.0
        for attr in ("kcal", "protein", "carbs", "fat"):
            value = getattr(macros, attr)
            if value is not None:
                setattr(out, attr, getattr(out, attr) + value * ratio)
        out.resolved.append(ResolvedIngredient(label, grams, entry))

    for attr in ("kcal", "protein", "carbs", "fat"):
        setattr(out, attr, round(getattr(out, attr), 1))
    return out
