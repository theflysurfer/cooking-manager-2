"""Les préférences alimentaires pesantes — `cap`, `rotate`, `minimize`, `maximize`.

Elles ne bloquent pas un repas comme `forbidden` : elles se comptent sur une
portée (repas, jour, semaine) et se rendent avec leur compte, franchi ou non.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from cooking_manager.convives import _contains_term, _fold

COUNTED = ("cap", "rotate")
WEEK, DAY, MEAL = "week", "day", "meal"
COUNTABLE_UNITS = frozenset({"", "repas", "meal", "plat", "fois"})
_NEGATION = re.compile(r"\bsans\s+(?:\w+\s+){0,3}\w+")

@dataclass(frozen=True)
class Rule:
    kind: str
    target: str
    value: float | None = None
    unit: str = ""
    scope: str = WEEK
    person: str = ""
    reason: str = ""

@dataclass
class Check:
    rule: Rule
    count: int
    limit: float | None
    scope: str
    breached: bool
    measurable: bool = True
    hits: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "kind": self.rule.kind, "target": self.rule.target,
            "person": self.rule.person, "reason": self.rule.reason,
            "limit": self.limit, "unit": self.rule.unit, "scope": self.scope,
            "count": self.count, "breached": self.breached,
            "measurable": self.measurable, "hits": self.hits,
        }

def load_rules(rows) -> list[Rule]:
    """Lignes `dietary_preference` → règles. `no_restriction` ne se compte pas."""
    rules = []
    for row in rows:
        data = dict(row)
        kind = str(data.get("kind") or "")
        if kind == "no_restriction":
            continue
        value = data.get("value")
        rules.append(Rule(
            kind=kind,
            target=str(data.get("target") or ""),
            value=float(value) if value is not None else None,
            unit=str(data.get("unit") or ""),
            scope=str(data.get("scope") or WEEK) or WEEK,
            person=str(data.get("person") or ""),
            reason=str(data.get("reason") or ""),
        ))
    return rules

def _mentions(meal: dict, target: str) -> bool:
    """« compote sans sucres ajoutés » ne compte pas comme du sucre ajouté."""
    haystack = " ".join([
        str(meal.get("dish") or ""),
        " ".join(str(i) for i in meal.get("ingredients") or []),
    ])
    return _contains_term(_NEGATION.sub(" ", _fold(haystack)), target)

def check_preferences(
    meals: list[dict], rules: list[Rule], vocabulary: list[str] | None = None,
) -> list[Check]:
    """Un `Check` par règle. Le compte est TOUJOURS rendu, franchi ou non.

    `vocabulary` = tous les ingrédients connus. Une cible qui n'y apparaît nulle
    part ne peut pas être comptée : son zéro n'est pas un constat, et
    `measurable` le dit — sans lui, une règle visée sur une catégorie
    (« famille de protéine ») se lit comme respectée à chaque menu.
    """
    folded_vocabulary = [_fold(v) for v in vocabulary] if vocabulary else None
    checks = []
    for rule in rules:
        hits = [
            {"day": m.get("day"), "slot": m.get("slot"), "dish": m.get("dish")}
            for m in meals if rule.target and _mentions(m, rule.target)
        ]
        if rule.scope == DAY:
            per_day: dict[str, int] = {}
            for hit in hits:
                per_day[str(hit["day"])] = per_day.get(str(hit["day"]), 0) + 1
            count = max(per_day.values()) if per_day else 0
        else:
            count = len(hits)

        breached = False
        if rule.kind in COUNTED and rule.value is not None:
            breached = count > rule.value
        elif rule.kind == "maximize" and rule.value is not None:
            breached = count < rule.value

        measurable = True
        if rule.kind in COUNTED and rule.unit.lower() not in COUNTABLE_UNITS:
            measurable = False
            breached = False
        elif folded_vocabulary is not None and not hits:
            measurable = any(
                _contains_term(entry, rule.target) for entry in folded_vocabulary
            )

        checks.append(Check(rule=rule, count=count, limit=rule.value,
                            scope=rule.scope, breached=breached,
                            measurable=measurable, hits=hits))
    return checks
