from __future__ import annotations

import re

UNIT_ALIASES: dict[str, tuple[str, ...]] = {
    "g": ("g", "gr", "grammes", "gramme", "grams", "gram"),
    "kg": ("kg", "kilo", "kilos", "kilogram", "kilograms"),
    "ml": ("ml", "millilitres", "milliliters", "millilitre", "milliliter"),
    "cl": ("cl",),
    "dl": ("dl", "décilitre", "décilitres"),
    "l": ("l", "litre", "litres", "liter", "liters"),
    "c.s.": (
        "c.s.", "cs", "c. à soupe", "c à soupe", "cuillère à soupe",
        "cuillères à soupe", "cuil. à soupe", "càs", "c.à.s",
        "tablespoon", "tablespoons", "tbsp",
    ),
    "c.c.": (
        "c.c.", "cc", "c. à café", "c à café", "cuillère à café",
        "cuillères à café", "cuil. à café", "càc", "c.à.c",
        "teaspoon", "teaspoons", "tsp",
    ),
    "pincée": ("pincée", "pincées", "pinch", "pinches"),
    "sachet": ("sachet", "sachets", "packet", "packets"),
    "boîte": ("boîte", "boîtes", "boite", "boites", "can", "cans"),
    "pot": ("pot", "pots"),
    "brique": ("brique", "briques"),
    "pièce": ("pièce", "pièces", "unité", "unités", "piece", "pieces"),
    "scoop": ("scoop", "scoops", "dosette", "dosettes"),
    "tranche": ("tranche", "tranches", "slice", "slices"),
    "gousse": ("gousse", "gousses", "clove", "cloves"),
    "brin": ("brin", "brins", "sprig", "sprigs"),
    "botte": ("botte", "bottes", "bunch", "bunches"),
    "filet": ("filet", "filets"),
    "feuille": ("feuille", "feuilles", "leaf", "leaves"),
    "verre": ("verre", "verres"),
    "tasse": ("tasse", "tasses", "cup", "cups"),
    "qs": ("qs", "q.s."),
    "oz": ("oz", "ounce", "ounces"),
    "lb": ("lb", "lbs", "pound", "pounds"),
    "fl oz": ("fl oz", "fluid ounce", "fluid ounces"),
    "stick": ("stick", "sticks"),
}

UNIT_LOOKUP: dict[str, str] = {
    variant.lower(): canonical
    for canonical, variants in UNIT_ALIASES.items()
    for variant in variants
}

UNIT_PATTERN = "|".join(
    re.escape(v) for v in sorted(UNIT_LOOKUP, key=len, reverse=True)
)

VULGAR_FRACTIONS: dict[str, str] = {
    "½": "0.5", "⅓": "0.333", "⅔": "0.667", "¼": "0.25", "¾": "0.75",
    "⅕": "0.2", "⅖": "0.4", "⅗": "0.6", "⅘": "0.8", "⅙": "0.167",
    "⅚": "0.833", "⅛": "0.125", "⅜": "0.375", "⅝": "0.625", "⅞": "0.875",
}


def expand_fractions(text: str) -> str:
    for glyph, value in VULGAR_FRACTIONS.items():
        text = re.sub(
            rf"(\d)\s*{glyph}",
            lambda m, v=value: str(float(m.group(1)) + float(v)),
            text,
        )
        text = text.replace(glyph, value)
    return text
