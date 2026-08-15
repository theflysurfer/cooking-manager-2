"""Macros d'une recette, calculées depuis ses ingrédients.

Ce module n'invente **aucune** donnée nutritionnelle. Il applique les règles
déjà écrites par le Coach Nutrition du vault (`Coaches/Coach Nutrition/_coach.md`) :

* **Règle 1 — pas d'hypothèse, que des données.** « Ne JAMAIS deviner les macros
  d'un aliment → base aliments Obsidian d'abord, internet en dernier recours. »
  Ici : un ingrédient qu'on ne sait pas résoudre ressort en `unresolved`, avec
  son motif. Il n'est jamais estimé au jugé, et jamais omis en silence.

* **Règle 2bis — réconciliation kcal vs macros** (erreur #25, 18/05/2026) :
  `kcal_reconstitué = P×4 + G×4 + L×9`, et au-delà de 5 % d'écart on présente
  **les deux chiffres**. Les fiches CIQUAL et les bases produit ont 5 à 15 %
  d'écart structurel (eau, cendres, fibres, alcool hors somme des macros).

**Trois sources, par ordre de préséance décroissante** — c'est la hiérarchie du
coach, pas une invention :

| Rang | Source | Pourquoi ce rang |
|---|---|---|
| 1 | fiche `marques/` (étiquette) | mesurée sur le produit exact, vérifiée à la main |
| 2 | `shopping_product.nutrition` | étiquette aussi, mais scrapée du portail drive |
| 3 | fiche `generiques/` (ANSES CIQUAL) | référence générique, sans marque |
| 4 | *(rien)* | → `unresolved`, jamais une estimation silencieuse |

⚠️ **La couverture est une donnée de premier plan, pas une statistique.** Une
recette dont la moitié des ingrédients sont « 1 oignon » ne peut PAS avoir de
macros justes : les unités-pièce ne se convertissent pas en grammes sans un
poids unitaire qu'on n'a pas. Une somme partielle présentée comme un total est
exactement le « nombre faux avec l'aplomb d'un nombre juste » que la Règle 1
interdit — d'où `coverage` et `conclusive` rendus à l'appelant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .ingredients import normalize_name

# ── Conversion vers le gramme ────────────────────────────────────────
# ⚠️ Seules les unités réellement convertibles figurent ici. Les autres
# (pièce, gousse, tranche, botte, pincée…) dépendent d'un poids unitaire propre
# à chaque aliment : les convertir « à peu près » fabriquerait des macros
# fausses. Elles ressortent en `unresolved`.
GRAMS_PER_UNIT: dict[str, float] = {
    "g": 1.0,
    "kg": 1000.0,
    # Densité 1 assumée pour les liquides aqueux. Faux pour l'huile (0,92) et
    # le miel (1,4), mais l'écart reste sous le bruit des fiches elles-mêmes.
    "ml": 1.0,
    "cl": 10.0,
    "l": 1000.0,
    # Cuillères : volumes standard français.
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
    key: str                 # nom normalisé, clé d'appariement
    title: str
    forms: dict[str, Macros] # « 100g », ou « crues »/« cuites » quand la fiche distingue
    source: str              # « ANSES-Ciqual », « Étiquette », « drive »…
    kind: str                # « marque » | « generique » | « drive »
    statut: str = ""         # « complet » | « partiel » | « INCERTAINE »
    path: str = ""

    @property
    def rank(self) -> int:
        """Préséance : plus petit = plus fiable."""
        return {"marque": 1, "drive": 2, "generique": 3}.get(self.kind, 4)

    def macros_for(self, ingredient_name: str) -> tuple[Macros | None, str]:
        """Macros de la forme demandée, ou (None, motif) si on ne peut trancher.

        ⚠️ Ne JAMAIS choisir une forme par défaut quand la fiche en distingue
        plusieurs : entre lentilles crues (339 kcal) et cuites (116), deviner
        c'est se tromper d'un facteur 3 sans que rien ne le signale.
        """
        if len(self.forms) == 1:
            return next(iter(self.forms.values())), ""
        if not self.forms:
            return None, "fiche sans tableau /100 g"

        name = normalize_name(ingredient_name)
        for label, macros in self.forms.items():
            words = [w for w in label.replace("/", " ").split() if w]
            if any(w in FORM_WORDS and re.search(rf"\b{re.escape(w)}\b", name)
                   for w in words):
                return macros, ""
        return None, f"forme ambiguë ({' / '.join(self.forms)}) — préciser dans la recette"


@dataclass
class ResolvedIngredient:
    name: str
    grams: float | None
    entry: FoodEntry | None
    reason: str = ""         # rempli seulement si non résolu

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


# ── Règle 2bis — réconciliation ──────────────────────────────────────

def reconcile(kcal: float | None, protein: float | None,
              carbs: float | None, fat: float | None) -> dict:
    """Confronte les kcal annoncées à la somme des macros (Règle 2bis).

    Les fiches CIQUAL et les bases produit ont 5 à 15 % d'écart structurel :
    l'eau, les cendres, les fibres et l'alcool ne sont pas dans `P×4+G×4+L×9`.
    Un écart n'est donc PAS un bug — mais au-delà de 5 % il doit être montré,
    jamais lissé, sinon on annonce un dépassement sur un chiffre non réconcilié.
    """
    # ⚠️ Tester `None in (...)` ne restreint PAS les types pour l'analyseur —
    # il faut nommer chaque terme, sinon pyright refuse l'arithmétique en aval.
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


# ── Lecture de la base aliments du vault ─────────────────────────────

_FM_RE = re.compile(r"\A---\n(.*?)\n---", re.DOTALL)
_NUM_RE = re.compile(r"(\d+(?:[.,]\d+)?)")
_PER_100G_RE = re.compile(r"/\s*100\s*(?:g|ml)", re.IGNORECASE)

_METRIC_KEYS = {
    "energie": "kcal", "énergie": "kcal", "calories": "kcal", "kcal": "kcal",
    "proteines": "protein", "protéines": "protein", "p": "protein",
    "glucides": "carbs", "g": "carbs",
    "lipides": "fat", "l": "fat",
}

# Particules grammaticales : « huile d'olive » et « huile olive » désignent le
# même produit, mais leurs clés normalisées diffèrent — la fiche vient d'un nom
# de fichier (« huile-olive »), l'ingrédient d'une phrase.
# ⚠️ On ne retire QUE des mots-outils. Retirer un qualificatif (« fraîche »,
# « entier », « fumé ») produirait de FAUX appariements : crème fraîche ≠ crème,
# et un faux positif fait sauter un achat qu'on ne découvre qu'en cuisine.
_PARTICLES = frozenset({"de", "du", "des", "d", "l", "la", "le", "les",
                        "a", "au", "aux", "en"})


def match_key(name: str) -> str:
    """Clé d'appariement : nom normalisé, débarrassé des particules."""
    return " ".join(w for w in normalize_name(name).split() if w not in _PARTICLES)

# Mots qui distinguent deux formes d'un même aliment dans un en-tête de colonne.
FORM_WORDS = ("cuit", "cuite", "cuits", "cuites", "cru", "crue", "crus", "crues",
              "sec", "secs", "seche", "sechees", "egoutte", "egouttes")


def _first_number(text: str) -> float | None:
    m = _NUM_RE.search(text.replace("~", ""))
    return float(m.group(1).replace(",", ".")) if m else None


def _cells(line: str) -> list[str]:
    return [c.strip().strip("*").strip() for c in line.strip().strip("|").split("|")]


def parse_food_sheet(text: str) -> tuple[dict, dict[str, Macros]]:
    """Fiche markdown → (frontmatter, {forme: macros pour 100 g}).

    ⚠️ **La première colonne n'est PAS toujours « /100g ».** La fiche
    `lentilles.md` porte « Crues /100g » puis « Cuites /100g » : prendre la
    première donnait 339 kcal là où une recette veut les cuites à 116 — un
    facteur 3, silencieux. On lit donc l'en-tête, et on garde **toutes** les
    colonnes exprimées pour 100 g, indexées par le libellé de leur forme.

    Quand il y en a plusieurs, ce module ne tranche pas : c'est l'ingrédient
    qui doit nommer sa forme, sinon l'aliment ressort non résolu (Règle 1 —
    pas d'hypothèse).
    """
    fm: dict = {}
    m = _FM_RE.match(text)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip().strip('"')

    forms: dict[str, Macros] = {}
    columns: dict[int, str] = {}   # disposition « métriques en lignes »
    metric_cols: dict[int, str] = {}  # disposition TRANSPOSÉE
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
            # ⚠️ Certaines fiches sont TRANSPOSÉES : les lignes sont des
            # versions (« 0% MG », « 3.2% MG », « Entier ») et les colonnes des
            # métriques. Sans ce cas, `fromage-blanc.md` — trois versions dont
            # les kcal vont du simple au double — n'était pas chargée du tout,
            # en silence.
            metrics = {i: _METRIC_KEYS[c.lower()]
                       for i, c in enumerate(cells) if c.lower() in _METRIC_KEYS}
            if len(metrics) >= 3:
                metric_cols = metrics
            continue

        if metric_cols:
            label = cells[0].strip().lower()
            if not label or set(label) <= {"-", " "}:
                continue
            macros = forms.setdefault(label, Macros())
            for idx, key in metric_cols.items():
                if idx < len(cells) and getattr(macros, key) is None:
                    setattr(macros, key, _first_number(cells[idx]))
            continue

        key = _METRIC_KEYS.get(cells[0].lower())
        if not key:
            continue
        for idx, label in columns.items():
            if idx < len(cells) and getattr(forms[label], key) is None:
                setattr(forms[label], key, _first_number(cells[idx]))

    return fm, forms


_BASE_CACHE: dict[str, dict[str, FoodEntry]] = {}


def load_food_base_cached(root: Path) -> dict[str, FoodEntry]:
    """`load_food_base` mémoïsé.

    ⚠️ Sur le VPS la base aliments vit sur un mount **rclone FUSE** : lire ses
    ~240 fiches prend ~7 s. Le faire à chaque requête rendait l'endpoint
    inutilisable (et masquait les erreurs derrière des timeouts). Les fiches
    changent quelques fois par mois — le cache est vidé par `reset_food_cache()`
    quand on veut forcer la relecture.
    """
    key = str(root)
    if key not in _BASE_CACHE:
        _BASE_CACHE[key] = load_food_base(root)
    return _BASE_CACHE[key]


def reset_food_cache() -> None:
    _BASE_CACHE.clear()


def load_food_base(root: Path) -> dict[str, FoodEntry]:
    """Charge `aliments-vérifiés/` → index par nom normalisé.

    En cas d'homonymie, la fiche la plus fiable gagne (marque avant générique) :
    c'est la hiérarchie du coach, appliquée au moment de l'indexation.
    """
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
            continue  # fiche sans tableau exploitable

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


# ── Source 2 : les produits réellement achetés (portails drive) ──────
#
# Étiquette elle aussi, mais scrapée : elle décrit le produit EXACT acheté, ce
# qu'aucune fiche générique ne fait. Elle prime donc sur le générique CIQUAL et
# s'efface devant une fiche `marques/` vérifiée à la main.

_DRIVE_KEYS = {
    "valeur énergétique (kcal)": "kcal", "valeur energetique (kcal)": "kcal",
    "énergie (kcal)": "kcal", "kcal": "kcal",
    "protéines": "protein", "proteines": "protein",
    "glucides": "carbs",
    "matières grasses": "fat", "matieres grasses": "fat", "lipides": "fat",
}


def entry_from_product(name: str, nutrition: dict) -> FoodEntry | None:
    """Ligne `shopping_product` → fiche aliment, ou None si inexploitable.

    Les étiquettes françaises sont TOUJOURS pour 100 g : pas d'ambiguïté de
    forme, donc une seule entrée. Les valeurs arrivent en chaînes (« 4,9 g »,
    « < 0,5 g ») ; sur « < 0,5 » on retient 0,5 — borne haute, soit le bon côté
    de l'erreur quand on compte ce qu'on mange.
    """
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


# ── Appariement ──────────────────────────────────────────────────────

def match_entry(name_normalized: str, base: dict[str, FoodEntry]) -> FoodEntry | None:
    """Ingrédient → fiche. Exact d'abord, puis le préfixe le plus long.

    ⚠️ Pas d'appariement flou. « crème fraîche » ne doit pas rencontrer « crème
    de coco », et une distance de Levenshtein les rapprocherait. Un faux
    appariement produit un nombre faux et invisible — mieux vaut un
    `unresolved` que l'app pose en question.
    """
    name = match_key(name_normalized)
    if not name:
        return None
    if name in base:
        return base[name]

    best: FoodEntry | None = None
    for key, entry in base.items():
        # Le nom de l'ingrédient doit COMMENCER par la clé de la fiche :
        # « chevre tres sec » trouve « chevre », « chevre » ne prend pas
        # « chevre chaud sur toast ».
        if name.startswith(key + " ") or key == name:
            if best is None or len(key) > len(best.key):
                best = entry
    return best


def to_grams(qty, unit: str | None) -> float | None:
    """Quantité + unité → grammes, ou None si l'unité n'est pas convertible.

    ⚠️ `qty` n'est pas toujours un `float` : asyncpg rend les colonnes NUMERIC
    en `Decimal`, qui ne se multiplie pas par un flottant. Les tests unitaires
    passent des `float` et ne peuvent donc pas voir ce cas — il n'est apparu
    qu'à l'appel réel.
    """
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

        # Un ingrédient optionnel absent du plat ne doit pas grever la couverture,
        # mais il ne compte pas non plus dans les macros — on l'écarte.
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
