"""Extraction des ingrédients et des étapes depuis le corps markdown d'une recette."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

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

_UNIT_LOOKUP: dict[str, str] = {
    variant.lower(): canonical
    for canonical, variants in UNIT_ALIASES.items()
    for variant in variants
}
_UNIT_PATTERN = "|".join(
    re.escape(v) for v in sorted(_UNIT_LOOKUP, key=len, reverse=True)
)

_QTY = r"(?:~|env\.?\s*)?(\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?)(?:\s*[-–—]\s*(\d+(?:[.,]\d+)?))?"

_INGREDIENT_RE = re.compile(
    rf"^\s*{_QTY}\s*(?:({_UNIT_PATTERN})(?!\w))?\s*(?:de\s+|d'|du\s+|des\s+)?(.*)$",
    re.IGNORECASE,
)

_OPTIONAL_RE = re.compile(r"\boptionnel(?:le)?\b|\bfacultatif\b|\bau choix\b", re.IGNORECASE)

_VULGAR_FRACTIONS = {
    "½": "0.5", "⅓": "0.333", "⅔": "0.667", "¼": "0.25", "¾": "0.75",
    "⅕": "0.2", "⅖": "0.4", "⅗": "0.6", "⅘": "0.8", "⅙": "0.167",
    "⅚": "0.833", "⅛": "0.125", "⅜": "0.375", "⅝": "0.625", "⅞": "0.875",
}

_WORD_ONE = re.compile(r"\bd[eu']?\s*(?:un|une)\b", re.IGNORECASE)

def _expand_fractions(text: str) -> str:
    """« ½ » → « 0.5 », et « 1 ½ » → « 1.5 » (quantité mixte)."""
    for glyph, value in _VULGAR_FRACTIONS.items():
        text = re.sub(rf"(\d)\s*{glyph}", lambda m, v=value: str(float(m.group(1)) + float(v)), text)
        text = text.replace(glyph, value)
    return text

_NUM_PREFIX = r"(?:\d+[.)]\s*)?"
_H_INGREDIENTS = re.compile(rf"^#{{2,3}}\s*{_NUM_PREFIX}(?:🥕\s*)?ingr[ée]dients?\b", re.IGNORECASE)
_H_STEPS = re.compile(
    rf"^#{{2,3}}\s*{_NUM_PREFIX}(?:👩‍🍳\s*|🔪\s*)?"
    r"(?:pr[ée]paration|instructions?|[ée]tapes?|recette|ex[ée]cution)\b",
    re.IGNORECASE,
)
_H_ANY = re.compile(r"^(#{1,6})\s")

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

_LIGATURES = str.maketrans({"œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE"})

PREPARATIONS: tuple[str, ...] = (
    "cisele", "emince", "hache", "rape", "ecrase", "concasse", "coupe",
    "detaille", "tranche", "pele", "epluche", "egoutte", "rince", "essore",
    "denoyaute", "equeute", "effeuille", "presse", "battu", "fondu", "ramolli",
    "desosse", "vide", "ecaille", "decortique", "trempe", "reveille",
)

_PREPARATION_TAIL = re.compile(
    r",\s*(?:"
    r"(?:et\s+|puis\s+)?(?:" + "|".join(PREPARATIONS) + r")(?:e?s?)"
    r"|en\s+(?:gros\s+|petits?\s+|fines?\s+|demi[-\s])?"
    r"(?:des|cubes?|tranches?|rondelles?|lanieres?|lamelles?|morceaux|quartiers?|batonnets?|julienne|deux|quatre)"
    r")\b.*$"
)

def _display_name(name: str | None) -> str:
    """Nom AFFICHABLE : sans la glose qui suit le tiret cadratin."""
    text = re.sub(r"\s+[–—]\s+.*$", "", name or "")
    text = re.sub(r"[*_`]", "", text)
    return text.strip(" .,;")

def normalize_name(name: str) -> str:
    """Nom d'ingrédient → forme comparable, clé d'appariement avec le garde-manger."""
    text = re.sub(r"\([^)]*\)", " ", name)
    text = re.sub(r"\s+[-–—]\s+.*$", "", text)
    text = text.translate(_LIGATURES)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"\b(bio|nature|en poudre|premium|label rouge|aop|igp)\b", " ", text)
    text = _PREPARATION_TAIL.sub(" ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(_singular(word) for word in text.split())

INVARIABLE_IN_S: frozenset[str] = frozenset({
    "pois", "ananas", "jus", "dos", "anis", "cassis", "repas", "mais",
    "couscous", "houmous", "ris", "os", "temps", "corps", "brebis", "souris",
    "tapas", "vermicelles", "bruxelles", "paris",
    "frais", "epais", "gras", "bas", "divers", "chips",
    "sans", "puis", "trois", "apres", "tres", "moins", "plus",
})

def _singular(word: str) -> str:
    """« oignons » → « oignon ». Les invariables en -s sont une liste fermée."""
    if word in INVARIABLE_IN_S or word.isdigit() or len(word) < 4:
        return word
    if word.endswith("ss") or not word.endswith("s"):
        return word
    return word[:-1]

def _clean_markup(text: str) -> str:
    """Retire le balisage markdown résiduel (gras, italique, code)."""
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    cleaned = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", cleaned)
    cleaned = re.sub(r"`(.+?)`", r"\1", cleaned)
    return cleaned.strip()

def _to_float(raw: str | None) -> float | None:
    if not raw:
        return None
    value = raw.replace(",", ".").strip()
    if "/" in value:
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

    clean = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    clean = _expand_fractions(clean)

    m = _INGREDIENT_RE.match(clean)
    if not m:
        ing.name = clean
        ing.name_normalized = normalize_name(clean)
        return ing

    qty_min, qty_max, unit, name = m.groups()
    ing.qty_min = _to_float(qty_min)
    ing.qty_max = _to_float(qty_max) if qty_max else ing.qty_min
    ing.unit = _UNIT_LOOKUP.get((unit or "").lower()) if unit else None
    ing.name = _display_name(name)
    ing.name_normalized = normalize_name(ing.name)

    if ing.qty_min is not None and ing.unit is None and ing.name:
        ing.unit = "pièce"

    ing.parsed = ing.qty_min is not None and bool(ing.name)
    if not ing.name:
        ing.name = clean
        ing.name_normalized = normalize_name(clean)
        ing.parsed = False
    return ing

def _section(body: str, header: re.Pattern) -> list[str]:
    """Lignes d'une section, de son titre jusqu'au prochain titre DE MÊME RANG."""
    out: list[str] = []
    level: int | None = None
    for line in body.splitlines():
        if level is None:
            opening = _H_ANY.match(line)
            if opening and header.match(line):
                level = len(opening.group(1))
            continue
        deeper = _H_ANY.match(line)
        if deeper and len(deeper.group(1)) <= level:
            break
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
            content.steps.append(Step(position=position, text=_clean_markup(m.group(2))))
            continue
        bullet = _BULLET.match(line)
        if bullet and bullet.group(1).strip():
            position += 1
            content.steps.append(Step(position=position, text=_clean_markup(bullet.group(1))))

    return content
