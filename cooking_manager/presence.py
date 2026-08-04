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
# Cycle d'une semaine sur deux, ancré sur une semaine de référence AVEC enfants.
# Source : Convives.md §Garde alternée.
CUSTODY_REFERENCE_WEEK = date(2026, 3, 3)   # semaine du 3 mars 2026 = AVEC
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
    """Une période de vacances scolaires — pendant laquelle il n'y a PAS de cantine."""
    label: str
    start: date
    end: date

    def covers(self, day: date) -> bool:
        return self.start <= day <= self.end


@dataclass
class Absence:
    """Absence déclarée d'une personne (voyage, déplacement…)."""
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
    overrides: dict[str, list[str]] = field(default_factory=dict)  # "2026-08-04/lunch" -> noms

    def is_school_holiday(self, day: date) -> bool:
        return any(p.covers(day) for p in self.school_holidays)

    def holiday_label(self, day: date) -> str | None:
        for p in self.school_holidays:
            if p.covers(day):
                return p.label
        return None


def children_present_this_week(day: date, reference: date = CUSTODY_REFERENCE_WEEK) -> bool:
    """Semaine AVEC enfants ? Cycle déterministe d'une semaine sur deux."""
    monday = day - timedelta(days=day.weekday())
    ref_monday = reference - timedelta(days=reference.weekday())
    return ((monday - ref_monday).days // 7) % 2 == 0


def attendees(day: date, slot: str, ref: Referential | None = None) -> list[str]:
    """Qui mange, ce jour-là, à ce créneau.

    La cantine n'existe QUE hors vacances scolaires — c'est précisément l'oubli
    qui a produit l'erreur du 2026-08-04.
    """
    ref = ref or Referential()

    override = ref.overrides.get(f"{day.isoformat()}/{slot}")
    if override is not None:
        return list(override)

    people = list(ADULTS)
    if children_present_this_week(day):
        at_school_canteen = (
            slot == "lunch"
            and day.weekday() in (1, 3, 4)          # mardi, jeudi, vendredi
            and not ref.is_school_holiday(day)      # ⚠️ la condition qui manquait
        )
        if not at_school_canteen:
            people += list(CHILDREN)

    present = [p for p in people if not any(a.who == p and a.covers(day) for a in ref.absences)]

    # Un repas maison suppose au moins un adulte. Si tous sont absents, le repas
    # n'a pas lieu ici — mieux vaut le dire que de rendre une table composée des
    # seuls enfants, qui se lirait comme un repas à préparer.
    if not any(p in ADULTS for p in present):
        return []

    return present


def week_grid(monday: date, ref: Referential | None = None) -> list[dict]:
    """Grille de présence de la semaine, prête à afficher ou à ingérer."""
    ref = ref or Referential()
    out = []
    for offset in range(7):
        day = monday + timedelta(days=offset)
        row = {
            "day": _DAY_NAMES[offset],
            "date": day.isoformat(),
            "school_holiday": ref.holiday_label(day),
            "children_week": children_present_this_week(day),
        }
        for slot in SLOTS:
            row[slot] = attendees(day, slot, ref)
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
    """Corps de la section `## …keyword…`."""
    heads = list(_H2.finditer(body))
    for idx, head in enumerate(heads):
        if keyword.lower() in head.group(1).lower():
            end = heads[idx + 1].start() if idx + 1 < len(heads) else len(body)
            return body[head.end():end]
    return ""


def parse_referential(body: str) -> Referential:
    """`Presences.md` → référentiel exploitable. Tolérant : une section absente
    n'est pas une erreur, elle laisse simplement la trame déterministe s'appliquer."""
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
