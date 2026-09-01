"""Garde-manger : inventaire réel, et différentiel avec un besoin (ADR 0001)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from .ingredients import UNIT_ALIASES, normalize_name

STATUS_OK = "ok"
STATUS_LOW = "low"
STATUS_OUT = "out"

XSTATUS_MAP = {
    "ok": STATUS_OK,
    "low": STATUS_LOW,
    "urgent": STATUS_LOW,
    "out": STATUS_OUT,
    "a-jeter": STATUS_OUT,
    "à-jeter": STATUS_OUT,
    "perime": STATUS_OUT,
    "périmé": STATUS_OUT,
    "perime-conserve": STATUS_OUT,
    "périmé-conserve": STATUS_OUT,
    "verifier-dlc": STATUS_LOW,
    "vérifier-dlc": STATUS_LOW,
}

ENOUGH = "suffisant"
PARTIAL = "insuffisant"
MISSING = "absent"
UNKNOWN = "inconnu"

PERISHABLE_HINTS = ("frais", "légume", "legume", "fruit", "protéine", "proteine")

STALE_AFTER = timedelta(days=14)

_UNIT_LOOKUP = {
    variant.lower(): canonical
    for canonical, variants in UNIT_ALIASES.items()
    for variant in variants
}
_UNIT_PATTERN = "|".join(re.escape(v) for v in sorted(_UNIT_LOOKUP, key=len, reverse=True))

_TO_BASE = {"kg": ("g", 1000.0), "g": ("g", 1.0),
            "l": ("ml", 1000.0), "cl": ("ml", 10.0), "ml": ("ml", 1.0),
            "pièce": ("pièce", 1.0)}

_SECTION = re.compile(r"^##+\s+(.+?)\s*$", re.MULTILINE)
_ITEM = re.compile(r"^\s*-\s+(.+?)\s*$", re.MULTILINE)
_STATUS = re.compile(r"#\s*status\s*=\s*([\w\-àéèêëîïôöûü]+)", re.IGNORECASE)
_ENTERED = re.compile(r"entré\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
_QTY_IN_TEXT = re.compile(
    rf"(?<![\w.])(\d+(?:[.,]\d+)?)\s*(?:×|x)?\s*(?:(\d+(?:[.,]\d+)?)\s*)?({_UNIT_PATTERN})(?!\w)",
    re.IGNORECASE,
)


@dataclass
class PantryItem:
    rayon: str
    name: str
    name_normalized: str
    qty_text: str = ""
    qty_value: float | None = None
    unit: str | None = None
    status: str = STATUS_OK
    xstatus: str = "ok"
    entered_at: date | None = None
    raw: str = ""

    @property
    def is_perishable(self) -> bool:
        rayon = self.rayon.lower()
        return any(h in rayon for h in PERISHABLE_HINTS)


@dataclass
class Pantry:
    items: list[PantryItem] = field(default_factory=list)
    updated: date | None = None
    aliases: dict[str, str] = field(default_factory=dict)

    def age_days(self, today: date | None = None) -> int | None:
        if not self.updated:
            return None
        return ((today or date.today()) - self.updated).days

    def is_stale(self, today: date | None = None) -> bool:
        age = self.age_days(today)
        return age is not None and age > STALE_AFTER.days

    def find(self, normalized: str) -> PantryItem | None:
        """Appariement par groupe d'alias, puis repli par inclusion de MOT (ADR 0002)."""
        if not normalized:
            return None
        group = self._alias_group(normalized)
        exact = [i for i in self.items if i.name_normalized in group]
        if exact:
            return _best(exact)
        contains = [
            i for i in self.items
            if _contains_words(i.name_normalized, normalized)
            or _contains_words(normalized, i.name_normalized)
        ]
        if not contains:
            return None
        return _best(sorted(contains, key=lambda i: len(i.name_normalized)))

    def _alias_group(self, normalized: str) -> set[str]:
        """Graphies équivalentes à `normalized`, chaînes d'alias résolues jusqu'à leur racine."""
        root = self._alias_root(normalized)
        return {
            name for name in {normalized, root} | set(self.aliases)
            if self._alias_root(name) == root
        }

    def _alias_root(self, name: str) -> str:
        """Bout de la chaîne d'alias, insensible aux cycles."""
        seen = {name}
        while True:
            nxt = self.aliases.get(name)
            if nxt is None or nxt in seen:
                return name
            name = nxt
            seen.add(name)


def _contains_words(haystack: str, needle: str) -> bool:
    """`needle` apparaît-il dans `haystack` sur des frontières de mot ?"""
    if not needle or not haystack:
        return False
    return re.search(r"(?:^|\s)" + re.escape(needle) + r"(?:\s|$)", haystack) is not None


def _best(candidates: list[PantryItem]) -> PantryItem:
    """Entre plusieurs lignes du même produit, la mieux dotée gagne."""
    order = {STATUS_OK: 0, STATUS_LOW: 1, STATUS_OUT: 2}
    return sorted(candidates, key=lambda i: order.get(i.status, 3))[0]


def _parse_qty(text: str) -> tuple[float | None, str | None]:
    """« 2×100 g » → (200, g) · « 480 g / 4 filets » → (480, g) · « en stock » → (None, None)."""
    m = _QTY_IN_TEXT.search(text)
    if not m:
        return None, None
    first = float(m.group(1).replace(",", "."))
    second = float(m.group(2).replace(",", ".")) if m.group(2) else None
    unit = _UNIT_LOOKUP.get(m.group(3).lower())
    return (first * second if second else first), unit


_FRONTMATTER_UPDATED = re.compile(
    r"^---\s*$.*?^\s*updated\s*:\s*[\"']?(\d{4}-\d{2}-\d{2})",
    re.MULTILINE | re.DOTALL,
)


def parse_pantry(body: str, updated: date | None = None) -> Pantry:
    """Corps de `Garde-manger.md` → inventaire daté, la date étant lue à défaut du frontmatter."""
    pantry = Pantry(updated=updated)
    if not body:
        return pantry

    if pantry.updated is None:
        fm = _FRONTMATTER_UPDATED.search(body)
        if fm:
            try:
                pantry.updated = date.fromisoformat(fm.group(1))
            except ValueError:
                pantry.updated = None

    sections = list(_SECTION.finditer(body))
    for idx, sec in enumerate(sections):
        rayon = sec.group(1).strip()
        end = sections[idx + 1].start() if idx + 1 < len(sections) else len(body)
        for item in _ITEM.finditer(body[sec.end():end]):
            line = item.group(1).strip()
            if not line or line.startswith(("[", "!", "**Note")):
                continue

            xstatus = "ok"
            sm = _STATUS.search(line)
            if sm:
                xstatus = sm.group(1).strip().lower()
            status = XSTATUS_MAP.get(xstatus, STATUS_OK)

            entered = None
            em = _ENTERED.search(line)
            if em:
                try:
                    entered = date.fromisoformat(em.group(1))
                except ValueError:
                    entered = None

            head = re.split(r"\s+[—–]\s+", line, maxsplit=1)
            name = re.sub(r"\*\*", "", head[0]).strip()
            name = re.sub(r"#\s*status\s*=\s*[\w\-àéèêëîïôöûü]+", "", name)
            name = re.sub(r"\(entré[^)]*\)", "", name)
            name = re.sub(r"\(constaté[^)]*\)", "", name).strip()
            qty_text = head[1] if len(head) > 1 else ""
            qty_text = re.sub(r"#.*$", "", qty_text)
            qty_text = re.sub(r"\(entré[^)]*\)", "", qty_text).strip(" |")

            if not name:
                continue

            qty_value, unit = _parse_qty(qty_text)
            pantry.items.append(PantryItem(
                rayon=rayon, name=name, name_normalized=normalize_name(name),
                qty_text=qty_text, qty_value=qty_value, unit=unit,
                status=status, xstatus=xstatus, entered_at=entered, raw=line,
            ))

    return pantry


@dataclass
class Need:
    """Un ingrédient requis, consolidé sur l'ensemble du menu."""
    name: str
    name_normalized: str
    qty: float | None = None
    unit: str | None = None
    recipes: list[str] = field(default_factory=list)
    is_optional: bool = True
    raw_lines: list[str] = field(default_factory=list)


@dataclass
class Verdict:
    need: Need
    outcome: str
    pantry_item: PantryItem | None = None
    reason: str = ""
    to_buy: float | None = None
    assumed_empty: bool = False


def _comparable(need: Need, item: PantryItem) -> bool:
    """Les quantités ne se comparent que si les unités sont commensurables."""
    if need.qty is None or item.qty_value is None:
        return False
    if not need.unit or not item.unit:
        return False
    a, b = _TO_BASE.get(need.unit), _TO_BASE.get(item.unit)
    return bool(a and b and a[0] == b[0])


_SPOON_SCALE = {"c.s.", "c.c.", "pincée", "trait", "filet", "goutte"}


def _to_base(qty: float, unit: str) -> float:
    return qty * _TO_BASE[unit][1]


def check_need(need: Need, pantry: Pantry, today: date | None = None) -> Verdict:
    """Un besoin + l'inventaire → un verdict, et jamais un silence."""
    item = pantry.find(need.name_normalized)

    if item is None:
        return Verdict(need, MISSING, None, "absent du garde-manger", need.qty)

    if item.status == STATUS_OUT:
        return Verdict(need, MISSING, item, f"marqué épuisé ({item.xstatus})", need.qty)

    if pantry.is_stale(today) and item.is_perishable:
        return Verdict(
            need, UNKNOWN, item,
            f"inventaire vieux de {pantry.age_days(today)} jours — produit frais supposé épuisé",
            need.qty, assumed_empty=True,
        )

    if item.status == STATUS_LOW and not _comparable(need, item):
        return Verdict(need, PARTIAL, item, f"stock faible ({item.xstatus})", need.qty)

    if item.status == STATUS_OK and need.unit in _SPOON_SCALE:
        return Verdict(need, ENOUGH, item,
                       f"présent en stock ({item.qty_text or 'quantité non chiffrée'}) — "
                       f"un besoin de {need.qty} {need.unit} s'y prélève")

    if need.qty is None:
        return Verdict(need, ENOUGH, item,
                       f"présent en stock ({item.qty_text or 'quantité non chiffrée'})")

    if not _comparable(need, item):
        return Verdict(
            need, UNKNOWN, item,
            f"présent ({item.qty_text or 'quantité non chiffrée'}) — "
            f"besoin de {need.qty} {need.unit or ''}, comparaison impossible".strip(),
        )

    have = _to_base(item.qty_value, item.unit)      # type: ignore[arg-type]
    want = _to_base(need.qty, need.unit)            # type: ignore[arg-type]
    if have >= want:
        return Verdict(need, ENOUGH, item, f"{item.qty_text} en stock, suffisant")

    remaining = want - have
    factor = _TO_BASE[need.unit][1]                 # type: ignore[index]
    return Verdict(
        need, PARTIAL, item,
        f"{item.qty_text} en stock, il en manque",
        round(remaining / factor, 2),
    )


def build_needs(meals_recipes: list[tuple[str, list, float]]) -> list[Need]:
    """Consolide (titre, ingrédients, ratio de portions) en besoins uniques par famille d'unité."""
    needs: dict[tuple[str, str], Need] = {}
    for title, ingredients, ratio in meals_recipes:
        for raw_ing in ingredients:
            ing = _as_mapping(raw_ing)
            key = ing.get("name_normalized") or normalize_name(ing.get("name", ""))
            if not key:
                continue

            unit = ing.get("unit")
            family = _TO_BASE[unit][0] if unit in _TO_BASE else (unit or "")
            need = needs.get((key, family))
            if need is None:
                need = Need(name=ing.get("name", ""), name_normalized=key, unit=unit)
                needs[(key, family)] = need

            qty = ing.get("qty_max") or ing.get("qty_min")
            if qty is not None:
                if need.unit is None:
                    need.unit = unit
                need.qty = (need.qty or 0) + float(qty) * ratio

            if not ing.get("is_optional"):
                need.is_optional = False
            if title not in need.recipes:
                need.recipes.append(title)
            if not ing.get("parsed") and ing.get("raw"):
                need.raw_lines.append(ing["raw"])

    return sorted(needs.values(), key=lambda n: (n.is_optional, n.name))


def _as_mapping(ing) -> dict:
    """Accepte indifféremment une ligne de DB (mapping) et un `Ingredient`."""
    if hasattr(ing, "get"):
        return ing
    return {
        "name": getattr(ing, "name", ""),
        "name_normalized": getattr(ing, "name_normalized", "") or "",
        "qty_min": getattr(ing, "qty_min", None),
        "qty_max": getattr(ing, "qty_max", None),
        "unit": getattr(ing, "unit", None),
        "is_optional": getattr(ing, "is_optional", False),
        "parsed": getattr(ing, "parsed", True),
        "raw": getattr(ing, "raw", ""),
    }
