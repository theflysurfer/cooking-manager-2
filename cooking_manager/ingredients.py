"""Extraction des ingrédients et des étapes depuis le corps markdown d'une recette.

Les recettes du vault ne portent leurs ingrédients que dans le texte :

    ## Ingrédients (1 pot Creami, ~490 g de mix)

    - 350 g skyr nature 0%
    - 2–3 c.s. lait entier (ajustement fluidité)
    - 1 c.c. miel (optionnel — goûter d'abord sans)

Sans structuration, impossible de générer une liste de courses ni de croiser
avec le garde-manger. C'est le prérequis dur du flux menu → panier.

**Principe de tolérance** : toute ligne qui résiste au parsing conserve son
`raw` et reste affichable telle quelle. Une quantité non comprise doit se voir
à l'écran, jamais disparaître — un ingrédient avalé en silence, c'est un achat
manqué qu'on découvre en cuisine.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# ── Unités reconnues ─────────────────────────────────────────────────
# Clé = forme canonique, valeurs = variantes rencontrées dans le vault.
UNIT_ALIASES: dict[str, tuple[str, ...]] = {
    "g": ("g", "gr", "grammes", "gramme"),
    "kg": ("kg", "kilo", "kilos"),
    "ml": ("ml", "millilitres"),
    "cl": ("cl",),
    "l": ("l", "litre", "litres"),
    "c.s.": ("c.s.", "cs", "c. à soupe", "c à soupe", "cuillère à soupe",
             "cuillères à soupe", "cuil. à soupe", "càs", "c.à.s"),
    "c.c.": ("c.c.", "cc", "c. à café", "c à café", "cuillère à café",
             "cuillères à café", "cuil. à café", "càc", "c.à.c"),
    "pincée": ("pincée", "pincées"),
    "sachet": ("sachet", "sachets"),
    "boîte": ("boîte", "boîtes", "boite", "boites"),
    "pot": ("pot", "pots"),
    "brique": ("brique", "briques"),
    "pièce": ("pièce", "pièces", "unité", "unités"),
    "scoop": ("scoop", "scoops", "dosette", "dosettes"),
    "tranche": ("tranche", "tranches"),
    "gousse": ("gousse", "gousses"),
    "brin": ("brin", "brins"),
    "botte": ("botte", "bottes"),
    "filet": ("filet", "filets"),
    "qs": ("qs", "q.s."),
}

# Trié par longueur décroissante : « c. à soupe » doit gagner sur « c. ».
_UNIT_LOOKUP: dict[str, str] = {
    variant.lower(): canonical
    for canonical, variants in UNIT_ALIASES.items()
    for variant in variants
}
_UNIT_PATTERN = "|".join(
    re.escape(v) for v in sorted(_UNIT_LOOKUP, key=len, reverse=True)
)

# Quantité : « 350 », « ~300 », « 2–3 », « 1/2 », « 1,5 ». Le tiret peut être
# un vrai tiret, un demi-cadratin ou un cadratin — le vault mélange les trois.
_QTY = r"(?:~|env\.?\s*)?(\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?)(?:\s*[-–—]\s*(\d+(?:[.,]\d+)?))?"

# ⚠️ `(?!\w)` et surtout PAS `\b` : les unités qui finissent par un point
# (« c.c. », « c.s. », « q.s. ») ne peuvent jamais satisfaire `\b`, puisque le
# point ET l'espace qui suit sont tous deux non-alphanumériques — il n'y a donc
# aucune frontière de mot entre eux. Avec `\b`, « 1 c.c. extrait de vanille »
# ressortait en unité « pièce » et nom « c.c. extrait de vanille ».
_INGREDIENT_RE = re.compile(
    rf"^\s*{_QTY}\s*(?:({_UNIT_PATTERN})(?!\w))?\s*(?:de\s+|d'|du\s+|des\s+)?(.*)$",
    re.IGNORECASE,
)

_OPTIONAL_RE = re.compile(r"\boptionnel(?:le)?\b|\bfacultatif\b|\bau choix\b", re.IGNORECASE)

# Le vault écrit « ½ oignon rouge », « ¼ de citron » avec les caractères
# typographiques — invisibles d'une regex numérique.
_VULGAR_FRACTIONS = {
    "½": "0.5", "⅓": "0.333", "⅔": "0.667", "¼": "0.25", "¾": "0.75",
    "⅕": "0.2", "⅖": "0.4", "⅗": "0.6", "⅘": "0.8", "⅙": "0.167",
    "⅚": "0.833", "⅛": "0.125", "⅜": "0.375", "⅝": "0.625", "⅞": "0.875",
}

# « Jus d'un ½ citron », « Zeste d'1 citron » : l'article porte la quantité.
_WORD_ONE = re.compile(r"\bd[eu']?\s*(?:un|une)\b", re.IGNORECASE)


def _expand_fractions(text: str) -> str:
    """« ½ » → « 0.5 », et « 1 ½ » → « 1.5 » (quantité mixte)."""
    for glyph, value in _VULGAR_FRACTIONS.items():
        # Quantité mixte collée : « 1½ » ou « 1 ½ ».
        text = re.sub(rf"(\d)\s*{glyph}", lambda m, v=value: str(float(m.group(1)) + float(v)), text)
        text = text.replace(glyph, value)
    return text

# Sections. Les titres portent souvent une parenthèse : « ## Ingrédients (4 portions) ».
_H_INGREDIENTS = re.compile(r"^#{2,3}\s*(?:🥕\s*)?ingr[ée]dients?\b", re.IGNORECASE)
_H_STEPS = re.compile(r"^#{2,3}\s*(?:👩‍🍳\s*|🔪\s*)?(?:pr[ée]paration|instructions?|[ée]tapes?|recette)\b",
                      re.IGNORECASE)
_H_ANY = re.compile(r"^#{1,6}\s")

_BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
_NUMBERED = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")


@dataclass
class Ingredient:
    position: int
    raw: str
    qty_min: float | None = None
    qty_max: float | None = None
    unit: str | None = None
    name: str = ""
    name_normalized: str = ""
    is_optional: bool = False
    parsed: bool = False


@dataclass
class Step:
    position: int
    text: str


@dataclass
class RecipeContent:
    ingredients: list[Ingredient] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)

    @property
    def parse_rate(self) -> float:
        if not self.ingredients:
            return 1.0
        return sum(1 for i in self.ingredients if i.parsed) / len(self.ingredients)


def normalize_name(name: str) -> str:
    """Nom d'ingrédient → forme comparable, clé d'appariement avec le garde-manger.

    « Miel bio (liquide) » et « miel » doivent se rencontrer. On retire les
    accents, les parenthèses, la ponctuation et les qualificatifs de conditionnement.
    """
    text = re.sub(r"\([^)]*\)", " ", name)           # parenthèses = précisions
    text = re.sub(r"\s+[-–—]\s+.*$", "", text)       # « — optionnel », « — qs »
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    # ⚠️ Ne retirer QUE ce qui ne change jamais l'identité du produit.
    # « fraîche », « entier », « liquide », « surgelé » en font partie :
    # crème fraîche ≠ crème, lait entier ≠ lait demi-écrémé, abricots congelés
    # ≠ abricots frais. Les retirer produirait de FAUX appariements avec le
    # garde-manger — et un faux positif fait sauter un achat nécessaire, ce qui
    # ne se découvre qu'en cuisine. Sur-normaliser est le mauvais côté de
    # l'erreur : mieux vaut un « inconnu » que l'app pose en question.
    text = re.sub(r"\b(bio|nature|en poudre|premium|label rouge|aop|igp)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _to_float(raw: str | None) -> float | None:
    if not raw:
        return None
    value = raw.replace(",", ".").strip()
    if "/" in value:  # fractions : « 1/2 »
        try:
            num, den = (p.strip() for p in value.split("/", 1))
            return round(float(num) / float(den), 4)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_ingredient(raw: str, position: int) -> Ingredient:
    """Une ligne → un ingrédient structuré. Ne lève jamais : au pire `parsed=False`."""
    text = raw.strip().lstrip("-*+ ").strip()
    ing = Ingredient(position=position, raw=text)
    ing.is_optional = bool(_OPTIONAL_RE.search(text))

    # Le gras markdown n'est que de la mise en forme.
    clean = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    clean = _expand_fractions(clean)

    m = _INGREDIENT_RE.match(clean)
    if not m:
        # Pas de quantité : « Sel, poivre », « Édulcorant au choix ».
        ing.name = clean
        ing.name_normalized = normalize_name(clean)
        return ing

    qty_min, qty_max, unit, name = m.groups()
    ing.qty_min = _to_float(qty_min)
    ing.qty_max = _to_float(qty_max) if qty_max else ing.qty_min
    ing.unit = _UNIT_LOOKUP.get((unit or "").lower()) if unit else None
    ing.name = (name or "").strip(" .,;")
    ing.name_normalized = normalize_name(ing.name)

    # « 2 bananes bien mûres » : pas d'unité explicite, l'unité est la pièce.
    if ing.qty_min is not None and ing.unit is None and ing.name:
        ing.unit = "pièce"

    ing.parsed = ing.qty_min is not None and bool(ing.name)
    if not ing.name:  # quantité seule, sans ingrédient → on rend la ligne brute
        ing.name = clean
        ing.name_normalized = normalize_name(clean)
        ing.parsed = False
    return ing


def _section(body: str, header: re.Pattern) -> list[str]:
    """Lignes d'une section, de son titre jusqu'au titre suivant."""
    lines = body.splitlines()
    out: list[str] = []
    inside = False
    for line in lines:
        if header.match(line):
            inside = True
            continue
        if inside and _H_ANY.match(line):
            break
        if inside:
            out.append(line)
    return out


def parse_recipe_body(body: str) -> RecipeContent:
    """Corps markdown → ingrédients + étapes."""
    content = RecipeContent()
    if not body:
        return content

    position = 0
    for line in _section(body, _H_INGREDIENTS):
        m = _BULLET.match(line)
        if not m:
            # Un paragraphe en gras clôt la liste : c'est une note
            # (« **Variantes testées par les sources** : … »), pas un ingrédient.
            if line.strip().startswith("**") and content.ingredients:
                break
            continue
        text = m.group(1).strip()
        if not text:
            continue
        position += 1
        content.ingredients.append(parse_ingredient(text, position))

    position = 0
    for line in _section(body, _H_STEPS):
        m = _NUMBERED.match(line)
        if m:
            position += 1
            content.steps.append(Step(position=position, text=m.group(2).strip()))
            continue
        bullet = _BULLET.match(line)
        if bullet and bullet.group(1).strip():
            position += 1
            content.steps.append(Step(position=position, text=bullet.group(1).strip()))

    return content
