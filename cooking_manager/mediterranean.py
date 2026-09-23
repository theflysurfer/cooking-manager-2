"""Couverture du cadre méditerranéen, dérivée des familles d'aliment (ADR 0033)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

FACET = "mediterranean_criteria"


@dataclass(frozen=True)
class Criterion:
    key: str
    code: str
    label: str
    satisfied_by: frozenset[str]
    reason: str = ""

    @property
    def in_reach(self) -> bool:
        """Sans famille d'aliment déclarée, aucun ingrédient ne peut le satisfaire."""
        return bool(self.satisfied_by)


def load_criteria() -> tuple[Criterion, ...]:
    """Les critères du vocabulaire épinglé — jamais une table écrite ici."""
    from .substitutions import load_vocabulary

    return tuple(
        Criterion(
            key=concept["key"],
            code=concept.get("code", ""),
            label=concept["label"],
            satisfied_by=frozenset(concept.get("satisfied_by") or ()),
            reason=concept.get("applicable_when") or "",
        )
        for concept in load_vocabulary().get(FACET) or []
    )


def cover(kinds_by_day: Mapping[str, Iterable[str]],
          criteria: Iterable[Criterion] | None = None) -> dict:
    """Jour par jour, les critères à portée que les familles d'aliment satisfont."""
    all_criteria = tuple(load_criteria() if criteria is None else criteria)
    in_reach = [c for c in all_criteria if c.in_reach]

    days = []
    for day in sorted(kinds_by_day):
        kinds = set(kinds_by_day[day])
        met = [c.key for c in in_reach if c.satisfied_by & kinds]
        days.append({
            "day": day,
            "met": met,
            "unmet": [c.key for c in in_reach if c.key not in met],
        })

    return {
        "criteria": [
            {
                "key": c.key, "code": c.code, "label": c.label,
                "satisfied_by": sorted(c.satisfied_by),
                "days_met": sum(1 for d in days if c.key in d["met"]),
                "days_total": len(days),
            }
            for c in in_reach
        ],
        "out_of_reach": [
            {"key": c.key, "code": c.code, "label": c.label, "reason": c.reason}
            for c in all_criteria if not c.in_reach
        ],
        "days": days,
    }
