"""La charge de travail d'un plat, DÉRIVÉE de ses étapes — facette `effort_bands`.

L'horloge ment : un mijoté de 50 min laisse les mains libres, un risotto de
35 min les occupe sans interruption. La bande se lit donc dans les gestes, pas
dans `total_time_min`.

Dérivée = `probation`. Elle ne devient un fait qu'une fois le plat réellement
tenu un soir de semaine, et ce verdict-là vit dans `service_context`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from cooking_manager.convives import _fold
from cooking_manager.substitutions import concept_keys

HANDS_OFF = "hands_off"
LIGHT = "light_hands_on"
HANDS_ON = "hands_on"
PROJECT = "project"

BANDS = (HANDS_OFF, LIGHT, HANDS_ON, PROJECT)
_WEIGHT = {HANDS_OFF: 0, LIGHT: 1, HANDS_ON: 2, PROJECT: 3}

_CONTINUOUS = re.compile(
    r"sans cesser de remuer|remuer sans (?:cesse|arret)|en remuant (?:constamment|sans arret)"
    r"|louche par louche|ne pas quitter|sans quitter|surveiller (?:de pres|constamment)"
    r"|tout en remuant"
)
_SHAPING = re.compile(
    r"faconner|former (?:des|les) (?:boulettes|quenelles)|farcir|petrir|abaisser"
    r"|rouler (?:les|la|des)|monter (?:le|la|les)|dresser en couches|chinois|tamiser"
)
_RESTING = re.compile(
    r"laisser reposer|reposer (?:au frais|une heure|[0-9]+\s*h)|la veille|une nuit"
    r"|mariner (?:[0-9]+\s*h|toute)"
)
"""Le repos est du TEMPS, pas de l'effort — mesuré sur les 104 recettes du corpus
le 2026-09-20 : le compter comme façonnage classait `overnight-oats` (5 min,
on mélange et on dort) en `project`, et 5 autres avec lui. Un repos long rend
au contraire les mains libres ; il relève de `service_contexts/next_day`."""
_PASSIVE = re.compile(
    r"enfourner|au four|laisser mijoter|a couvert|laisser cuire|couvrir et"
    r"|baisser le feu et laisser"
)

@dataclass(frozen=True)
class EffortReading:
    """Une bande, ses raisons, et le fait qu'elle soit dérivable ou non."""

    band: str
    derivable: bool
    markers: tuple[str, ...] = ()
    steps: int = 0

    def as_dict(self) -> dict:
        return {"band": self.band if self.derivable else None,
                "derivable": self.derivable, "markers": list(self.markers),
                "steps": self.steps}

def _hits(pattern: re.Pattern[str], text: str) -> list[str]:
    return [m.group(0) for m in pattern.finditer(text)]

def read_effort(steps: Sequence[str]) -> EffortReading:
    """La bande d'un plat, lue dans ses étapes. Sans étapes : rien, et on le dit."""
    cleaned = [str(s).strip() for s in steps if str(s).strip()]
    if not cleaned:
        return EffortReading(band=LIGHT, derivable=False)

    text = _fold(" ".join(cleaned))
    markers: list[str] = []

    shaping = _hits(_SHAPING, text)
    resting = _hits(_RESTING, text)
    continuous = _hits(_CONTINUOUS, text)
    passive = _hits(_PASSIVE, text)

    if shaping:
        band = PROJECT
        markers = shaping
    elif continuous:
        band = HANDS_ON
        markers = continuous
    elif passive or resting:
        band = HANDS_OFF
        markers = passive + resting
    else:
        band = LIGHT

    return EffortReading(band=band, derivable=True,
                         markers=tuple(dict.fromkeys(markers)), steps=len(cleaned))

WEEKNIGHT_CLOCK_MAX = 45
WEEKNIGHT_HANDS_ON_MAX = 20

def fits_weeknight(reading: EffortReading, total_time_min: int | None = None) -> bool | None:
    """Tient un soir de semaine ? `None` quand rien ne permet de trancher.

    Les deux axes comptent, et ni l'un ni l'autre ne suffit : le mafé est
    `light_hands_on` mais tient 50 min à table (refus de Julien, 2026-09-20),
    les œufs brouillés sont `hands_on` mais expédiés en 15 min.
    """
    if not reading.derivable:
        return None
    if reading.band == PROJECT:
        return False
    if total_time_min is None or total_time_min <= 0:
        return None
    if reading.band == HANDS_ON:
        return total_time_min <= WEEKNIGHT_HANDS_ON_MAX
    return total_time_min <= WEEKNIGHT_CLOCK_MAX

def declared_bands() -> frozenset[str]:
    """Les bandes de l'artefact épinglé — le code ne doit pas en inventer une."""
    return concept_keys("effort_bands")
