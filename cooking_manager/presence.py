"""Qui est présent à quel repas — le référentiel de présence.

Pourquoi ce module existe (incident 2026-08-04) : le menu programmait des wraps
au poulet un mardi midi alors que Clémence est pescétarienne. Deux causes
distinctes, et c'est la seconde qui est la plus vicieuse :

1. Aucun contrôle de compatibilité ne tournait (cf. `convives.py`).
2. **La composition de la table était devinée, pas calculée.** La grille type de
   `Convives.md` dit « mardi midi : enfants à la cantine » — mais elle porte la
   mention « **hors vacances scolaires** ». En août, elle ne s'applique pas, et
   raisonner dessus donne une réponse fausse avec l'aplomb d'une règle écrite.

**L'agenda seul ne suffit pas.** Vérifié le 2026-08-04 : la semaine ne portait
qu'un seul événement (« Semaine à Bordeaux » du 8 au 16). Rien sur la garde
alternée, rien sur les vacances, rien sur la cantine. Un export d'agenda
n'aurait donc rien rattrapé — il apporte les *exceptions*, pas la trame.

Trois sources, dans cet ordre de priorité croissante :

    trame déterministe (garde alternée × période scolaire)
      └─> absences déclarées (vault ou agenda)
            └─> override manuel explicite      ← gagne toujours
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

# ── Garde alternée ───────────────────────────────────────────────────
# Constantes historiques — fallback quand aucune HouseholdConfig n'est fournie.
CUSTODY_REFERENCE_WEEK = date(2026, 3, 3)
ADULTS = ("Julien", "Clémence")
CHILDREN = ("Léa", "Titouan")

SLOTS = ("breakfast", "lunch", "snack", "dinner")

_DAY_INDEX = {
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
    "vendredi": 4, "samedi": 5, "dimanche": 6,
}
_DAY_NAMES = list(_DAY_INDEX)


@dataclass
class SchoolPeriod:
    label: str
    start: date
    end: date

    def covers(self, day: date) -> bool:
        return self.start <= day <= self.end


@dataclass
class Absence:
    who: str
    start: date
    end: date
    reason: str = ""

    def covers(self, day: date) -> bool:
        return self.start <= day <= self.end


@dataclass
class Referential:
    school_holidays: list[SchoolPeriod] = field(default_factory=list)
    absences: list[Absence] = field(default_factory=list)
    overrides: dict[str, list[str]] = field(default_factory=dict)

    def is_school_holiday(self, day: date) -> bool:
        return any(p.covers(day) for p in self.school_holidays)

    def holiday_label(self, day: date) -> str | None:
        for p in self.school_holidays:
            if p.covers(day):
                return p.label
        return None


# ── Configuration du foyer (données DB ou fallback constantes) ──────

@dataclass
class CustodyInfo:
    name: str
    pattern: str = "alternating_weeks"
    reference_date: date = CUSTODY_REFERENCE_WEEK
    reference_present: bool = True

@dataclass
class CanteenEntry:
    name: str
    weekday: int
    slot: str = "lunch"
    active_outside_holidays: bool = True

@dataclass
class HouseholdConfig:
    adults: tuple[str, ...] = ADULTS
    children: list[CustodyInfo] = field(default_factory=lambda: [
        CustodyInfo(name=n) for n in CHILDREN
    ])
    canteen: list[CanteenEntry] = field(default_factory=lambda: [
        CanteenEntry(name=n, weekday=wd) for n in CHILDREN for wd in (1, 3, 4)
    ])


def children_present_this_week(day: date, reference: date = CUSTODY_REFERENCE_WEEK) -> bool:
    monday = day - timedelta(days=day.weekday())
    ref_monday = reference - timedelta(days=reference.weekday())
    return ((monday - ref_monday).days // 7) % 2 == 0


def _child_present(day: date, custody: CustodyInfo) -> bool:
    if custody.pattern == "always":
        return True
    if custody.pattern == "alternating_weeks":
        is_ref_week = children_present_this_week(day, custody.reference_date)
        return is_ref_week == custody.reference_present
    return True


def _child_at_canteen(
    child_name: str, day: date, slot: str,
    canteen: list[CanteenEntry], ref: Referential,
) -> bool:
    for ce in canteen:
        if ce.name != child_name or ce.weekday != day.weekday() or ce.slot != slot:
            continue
        if ce.active_outside_holidays and ref.is_school_holiday(day):
            return False
        return True
    return False


def attendees(
    day: date, slot: str,
    ref: Referential | None = None,
    household: HouseholdConfig | None = None,
) -> list[str]:
    ref = ref or Referential()
    hh = household or HouseholdConfig()

    override = ref.overrides.get(f"{day.isoformat()}/{slot}")
    if override is not None:
        return list(override)

    people = list(hh.adults)

    for child in hh.children:
        if not _child_present(day, child):
            continue
        if _child_at_canteen(child.name, day, slot, hh.canteen, ref):
            continue
        people.append(child.name)

    present = [p for p in people if not any(a.who == p and a.covers(day) for a in ref.absences)]

    adult_names = set(hh.adults)
    if not any(p in adult_names for p in present):
        return []

    return present


def week_grid(
    monday: date,
    ref: Referential | None = None,
    household: HouseholdConfig | None = None,
) -> list[dict]:
    ref = ref or Referential()
    hh = household or HouseholdConfig()
    out = []
    for offset in range(7):
        day = monday + timedelta(days=offset)
        row = {
            "day": _DAY_NAMES[offset],
            "date": day.isoformat(),
            "school_holiday": ref.holiday_label(day),
            "children_week": any(
                _child_present(day, c) for c in hh.children
            ),
        }
        for slot in SLOTS:
            row[slot] = attendees(day, slot, ref, hh)
        out.append(row)
    return out


# ── Lecture du référentiel depuis le vault ───────────────────────────

_PERIOD_ROW = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|",
    re.MULTILINE,
)
_ABSENCE_ROW = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^|]*)\|",
    re.MULTILINE,
)
_H2 = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _section(body: str, keyword: str) -> str:
    heads = list(_H2.finditer(body))
    for idx, head in enumerate(heads):
        if keyword.lower() in head.group(1).lower():
            end = heads[idx + 1].start() if idx + 1 < len(heads) else len(body)
            return body[head.end():end]
    return ""


def parse_referential(body: str) -> Referential:
    ref = Referential()

    for row in _PERIOD_ROW.finditer(_section(body, "vacances")):
        try:
            ref.school_holidays.append(SchoolPeriod(
                label=row.group(1).strip().strip("*"),
                start=date.fromisoformat(row.group(2)),
                end=date.fromisoformat(row.group(3)),
            ))
        except ValueError:
            continue

    for row in _ABSENCE_ROW.finditer(_section(body, "absence")):
        try:
            ref.absences.append(Absence(
                who=row.group(1).strip().strip("*"),
                start=date.fromisoformat(row.group(2)),
                end=date.fromisoformat(row.group(3)),
                reason=(row.group(4) or "").strip(),
            ))
        except ValueError:
            continue

    for line in _section(body, "exception").splitlines():
        m = re.match(r"^\s*-\s*(\d{4}-\d{2}-\d{2})/(\w+)\s*[:：]\s*(.+)$", line)
        if m:
            names = [n.strip() for n in re.split(r"[,+]", m.group(3)) if n.strip()]
            ref.overrides[f"{m.group(1)}/{m.group(2)}"] = names

    return ref
