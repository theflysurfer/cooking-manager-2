"""Produits et gammes refusés à l'achat — lecture de `shopping_preference`."""

from __future__ import annotations

from dataclasses import dataclass

from cooking_manager.convives import (
    EGG,
    FISH,
    MEAT,
    POULTRY,
    SEAFOOD,
    _contains_term,
    _fold,
)

PRODUCT = "blacklist"
BRAND = "blacklist_brand"

ANIMAL_PROTEIN = "animal_protein"
ANIMAL_TERMS = MEAT + POULTRY + FISH + SEAFOOD + EGG

@dataclass(frozen=True)
class Ban:
    kind: str
    key: str
    label: str
    reason: str
    scope: str = ""

    def as_dict(self) -> dict:
        return {"kind": self.kind, "key": self.key, "label": self.label,
                "reason": self.reason, "scope": self.scope}

def load_bans(rows) -> list[Ban]:
    """Lignes `shopping_preference` actives → bans. Les autres pref_type sont ignorés."""
    bans = []
    for row in rows:
        data = dict(row)
        if not data.get("active", True):
            continue
        pref_type = data.get("pref_type")
        if pref_type not in (PRODUCT, BRAND):
            continue
        key = str(data.get("key") or "")
        value = str(data.get("value") or "")
        reason = str(data.get("reason") or "")
        if pref_type == BRAND:
            bans.append(Ban(kind="brand", key=key, label=key, reason=reason,
                            scope=value.strip()))
        else:
            bans.append(Ban(kind="product", key=key, label=value or key, reason=reason))
    return bans

def is_animal_protein(product_name: str) -> bool:
    folded = _fold(product_name)
    return any(_contains_term(folded, term) for term in ANIMAL_TERMS)

def find_ban(
    product_name: str,
    bans: list[Ban],
    *,
    auchan_id: str | None = None,
    brand: str | None = None,
) -> Ban | None:
    """Le premier ban qui frappe ce produit, ou None. Produit d'abord, gamme ensuite."""
    folded_name = _fold(product_name or "")
    folded_brand = _fold(brand or "")
    ref = (auchan_id or "").strip().lower()

    for ban in bans:
        if ban.kind != "product" or not ban.key:
            continue
        key = ban.key.strip().lower()
        if ref and key == ref:
            return ban
        if _fold(ban.key) and _fold(ban.key) in folded_name:
            return ban

    for ban in bans:
        if ban.kind != "brand" or not ban.key:
            continue
        folded_key = _fold(ban.key)
        hit = folded_key and (folded_key in folded_brand or folded_key in folded_name)
        if not hit:
            continue
        if ban.scope == ANIMAL_PROTEIN and not is_animal_protein(product_name or ""):
            continue
        return ban
    return None
