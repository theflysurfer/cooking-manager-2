"""Profils alimentaires des convives, et contrôle de compatibilité d'un repas.

Le vault documente précisément qui mange quoi (`Noyau/Cuisine/Convives.md`) :
régimes, aversions, œufs refusés, interdits absolus. Mais **rien ne l'ingérait** :
la table `convive` était vide, donc l'app n'avait aucun moyen de savoir qu'un
plat posait problème à quelqu'un.

Incident fondateur (2026-08-04) : le menu de la semaine programmait « Wraps hack
poulet froid » un mardi midi alors que Clémence est **pescétarienne** — noté
noir sur blanc dans le vault depuis mai. Un seul repas de la semaine était en
faute, et personne ne l'a vu : le contrôle reposait entièrement sur le fait
qu'un humain y pense.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# ── Régimes → familles d'aliments exclues ────────────────────────────
# Volontairement large : mieux vaut une alerte à lever qu'un plat servi à
# quelqu'un qui ne peut pas le manger.

MEAT = (
    "viande", "boeuf", "bœuf", "steak", "porc", "agneau", "veau", "lapin",
    "jambon", "lardon", "bacon", "saucisse", "saucisson", "merguez", "chorizo",
    "salami", "charcuterie", "roti", "rôti", "hachis", "bolognaise", "carbonara",
    # ⚠️ « lard » manquait alors que « lardon » était là — et les termes sont
    # comparés en MOTS ENTIERS, donc « 8 tranches de lard fumé » ne rencontrait
    # aucune entrée. Deux recettes du livre de fromages passaient ainsi pour
    # compatibles pescétarien.
    "lard", "guanciale", "pancetta", "coppa", "grisons", "prosciutto",
    "mouton", "andouille", "boudin", "foie gras", "gesier", "gésier",
    # ⚠️ « rillettes » n'y est PAS, volontairement : les rillettes de THON du
    # vault sont compatibles pescétarien. L'ajouter bloquerait une recette
    # mangeable — le sur-blocage érode la confiance plus vite qu'un oubli.
)
POULTRY = ("volaille", "poulet", "dinde", "canard", "magret", "escalope de poulet", "pintade")
FISH = ("poisson", "saumon", "thon", "cabillaud", "lieu", "merlu", "merlan",
        "sardine", "maquereau", "truite", "colin", "anchois")
SEAFOOD = ("crevette", "gambas", "moule", "huitre", "huître", "calamar",
           "poulpe", "crabe", "saint-jacques", "surimi")
DAIRY = ("lait", "fromage", "beurre", "creme", "crème", "yaourt", "skyr",
         "ricotta", "feta", "mozzarella", "parmesan")
EGG = ("oeuf", "œuf")

# Plats dont le NOM implique la viande sans la nommer (carbonara → guanciale,
# bolognaise → bœuf haché). Un marqueur « végétarien/vegan » dans le libellé
# annule l'implication — « Tagliatelles carbonara végétarienne » est sans
# viande PAR DÉCLARATION (faux positif réel du menu Bègles, refs #61) — alors
# qu'un ingrédient explicite (« bacon », « lardon ») continue d'alerter même
# à côté du marqueur : mieux vaut une alerte de trop.
MEAT_IMPLIED_DISHES = frozenset({"bolognaise", "carbonara", "hachis"})

_VEGGIE_MARKER = re.compile(
    r"(?<!\w)(?:vegetarien(?:ne)?s?|vegetalien(?:ne)?s?|vegan|veggie)(?!\w)"
)

DIETS: dict[str, tuple[str, ...]] = {
    # pescétarien : pas de viande ni volaille, poisson et fruits de mer OK
    "pescetarian": MEAT + POULTRY,
    "vegetarian": MEAT + POULTRY + FISH + SEAFOOD,
    "vegan": MEAT + POULTRY + FISH + SEAFOOD + DAIRY + EGG,
    "semi-vegetarian": (),   # tolère tout, mais fréquence limitée — pas un veto
    "omnivore": (),
    "standard": (),
}

DIET_ALIASES: dict[str, str] = {
    "pescetarien": "pescetarian", "pescetarienne": "pescetarian",
    "pesco-vegetarien": "pescetarian", "pesco-mediterraneen": "pescetarian",
    "vegetarien": "vegetarian", "vegetarienne": "vegetarian",
    "vegetalien": "vegan", "vegan": "vegan",
    "semi-vegetarien": "semi-vegetarian",
    "omnivore": "omnivore", "standard": "standard",
}


# ⚠️ Les ligatures œ et æ n'ont AUCUNE décomposition Unicode — ni canonique ni
# de compatibilité. `NFKD` les laisse intactes, et `encode('ascii','ignore')` les
# SUPPRIME purement : « œuf » devenait « uf », « bœuf » devenait « buf ». Un
# terme « oeuf dur » ne pouvait donc jamais matcher un plat écrit « œuf dur »,
# et la salade niçoise passait devant Léa et Clémence qui refusent l'œuf dur.
# Le français culinaire en est plein (œuf, bœuf, cœur) : il faut les expanser
# explicitement AVANT le repli ASCII.
_LIGATURES = str.maketrans({"œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE"})


def _fold(text: str) -> str:
    """Minuscules sans accents ni ligatures — pour comparer des libellés libres."""
    expanded = str(text).translate(_LIGATURES)
    normalized = unicodedata.normalize("NFKD", expanded)
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


@dataclass
class Convive:
    name: str
    diet: str = "standard"
    dislikes: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)
    diet_exceptions: list[str] = field(default_factory=list)
    notes: str = ""
    is_guest: bool = False

    @property
    def diet_terms(self) -> list[str]:
        """Ce que le régime de cette personne interdit."""
        return list(DIETS.get(self.diet, ()))

    def diet_waived_on(self, folded_text: str) -> str | None:
        """L'exception qui dispense CE texte du régime — « quenelles de veau », pas « veau ».

        Porte sur une préparation, jamais sur un terme entier du régime : sans
        quoi lever les quenelles de veau laisserait aussi passer un rôti de veau.
        """
        for exception in self.diet_exceptions:
            if _contains_term(folded_text, _fold(exception)):
                return exception
        return None

    @property
    def excluded_terms(self) -> list[str]:
        """Tout ce qui doit déclencher une alerte pour cette personne."""
        return self.diet_terms + self.dislikes + self.forbidden


@dataclass
class Conflict:
    convive: str
    reason: str        # « régime pescetarian », « n'aime pas », « interdit »
    matched: str       # le terme trouvé dans le plat

    def __str__(self) -> str:
        return f"{self.convive} — {self.reason} : {self.matched}"


# ── Parsing de Convives.md ───────────────────────────────────────────

_PERSON = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
_FIELD = re.compile(r"^\s*-\s*\*\*(.+?)\*\*\s*[:：]\s*(.+?)\s*$", re.MULTILINE)
_FORBIDDEN_LINE = re.compile(r"^\s*-\s*❌\s*(.+?)\s*$", re.MULTILINE)
_GUEST_ROW = re.compile(r"^\|\s*\*\*(.+?)\*\*\s*\|([^|]*)\|([^|]*)\|([^|]*)\|", re.MULTILINE)
_GUESTS_HEADER = re.compile(r"^##\s+.*invit[ée]s?\s+r[ée]currents?", re.MULTILINE | re.IGNORECASE)
_NEXT_H2 = re.compile(r"^##\s+", re.MULTILINE)

# Entrées de tableaux qui ne sont pas des personnes — jours de la semaine et
# noms d'aliments, présents dans les autres tableaux du fichier.
_NOT_A_PERSON = {
    "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
    "mais", "oeufs durs", "ufs durs", "aliment", "jour", "personne",
}


def _guests_section(body: str) -> str:
    """Corps de la seule section « Invités récurrents »."""
    header = _GUESTS_HEADER.search(body)
    if not header:
        return ""
    rest = body[header.end():]
    nxt = _NEXT_H2.search(rest)
    return rest[: nxt.start()] if nxt else rest


def _split_list(value: str) -> list[str]:
    """« maïs, céleri, endive » → ['mais', 'celeri', 'endive »]."""
    cleaned = re.sub(r"\([^)]*\)", " ", value)
    cleaned = re.sub(r"\*\*", "", cleaned)
    parts = re.split(r"[,;·]|\bet\b|\bou\b", cleaned)
    out = []
    for part in parts:
        term = _fold(part).strip(" .·-—_")
        if term and len(term) > 2 and term not in {"rien", "aucune", "aucun", "non documente"}:
            out.append(term)
    return out


_REFUSES = re.compile(r"refuse\s+(.+)$", re.IGNORECASE)


def _parse_egg_refusals(value: str) -> list[str]:
    """« accepte coque, brouillés — **refuse dur, poché, au plat, mollet** »
    → ['oeuf dur', 'oeuf poche', 'oeuf au plat', 'oeuf mollet'].

    Les cuissons d'œufs refusées sont une contrainte réelle et fréquente chez
    Léa et Clémence, et elles apparaissent en clair dans les intitulés de plats
    (« Salade niçoise (thon, œuf dur…) »). Sans ce champ, une salade niçoise
    passe le contrôle alors que deux convives sur quatre ne peuvent pas la manger.
    """
    m = _REFUSES.search(_fold(value).replace("**", ""))
    if not m:
        return []
    out = []
    for prep in _split_list(m.group(1)):
        out.append(f"oeuf {prep}")
    return out


def _parse_diet(value: str) -> str:
    """⚠️ Alias les plus longs d'abord : « semi-vegetarien » contient
    « vegetarien ». Sans ce tri, Philippe et Béatrice — semi-végétariens qui
    mangent du poulet — passaient pour végétariens stricts, et tout plat carné
    déclenchait une fausse alerte."""
    folded = _fold(value)
    for alias in sorted(DIET_ALIASES, key=len, reverse=True):
        if alias in folded:
            return DIET_ALIASES[alias]
    return "standard"


def _contains_term(folded_text: str, term: str) -> bool:
    """Terme présent en tant que MOT, jamais en sous-chaîne.

    ⚠️ Sans frontières de mot, « maïs » matchait dans « hou­mous **mais**on » :
    l'assiette froide du vendredi ressortait en conflit pour Clémence et Léa
    alors qu'elle ne contient pas un grain de maïs. Un faux positif ruine la
    confiance dans l'alerte aussi sûrement qu'un faux négatif — et pousse à
    désactiver le contrôle.

    ⚠️ Le pluriel EST toléré, et seulement lui (« s » ou « x » final) : les
    termes du régime sont au singulier, si bien que « 200 g de lardons » et
    « 2 veaux » ne rencontraient aucune entrée et passaient pour compatibles.
    Aucun terme carné ne devient un autre mot en prenant sa marque de pluriel,
    donc « maison » reste hors d'atteinte de « maïs ».
    """
    if not term:
        return False
    return re.search(rf"(?<!\w){re.escape(term)}[sx]?(?!\w)", folded_text) is not None


def parse_convives(body: str) -> list[Convive]:
    """Corps de `Convives.md` → profils exploitables."""
    convives: list[Convive] = []
    if not body:
        return convives

    # Sections `### Prénom` de la partie « Famille ».
    matches = list(_PERSON.finditer(body))
    for idx, m in enumerate(matches):
        name = re.sub(r"\s*\(.*\)\s*$", "", m.group(1)).strip()
        if not name or name.lower().startswith(("règles", "regles", "aversions", "substituts",
                                                "semaine", "récap", "recap")):
            continue
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        section = body[m.end():end]

        convive = Convive(name=name)
        for field_match in _FIELD.finditer(section):
            label, value = _fold(field_match.group(1)), field_match.group(2)
            if label.startswith("regime"):
                convive.diet = _parse_diet(value)
            elif "n'aime pas" in label or "naime pas" in label:
                convive.dislikes = _split_list(value)
            elif label.startswith(("oeufs", "ufs")):
                convive.forbidden += _parse_egg_refusals(value)
        # ⚠️ `+=` et non `=` : la boucle ci-dessus a déjà pu remplir `forbidden`
        # avec les cuissons d'œufs refusées. Une réassignation les effacerait —
        # silencieusement, et le contrôle laisserait passer une salade niçoise
        # devant deux convives qui refusent l'œuf dur.
        convive.forbidden += [
            t for line in _FORBIDDEN_LINE.findall(section) for t in _split_list(line)
        ]
        convives.append(convive)

    # Table des invités récurrents — UNIQUEMENT celle-là.
    # ⚠️ Le fichier contient plusieurs tableaux markdown (aversions partagées,
    # rythme hebdomadaire, substituts de saveurs). Les balayer tous faisait
    # entrer « Maïs », « Mardi », « Mercredi »… dans le répertoire des convives,
    # avec des « interdits » absurdes. On borne à la section.
    guests_section = _guests_section(body)
    for row in _GUEST_ROW.finditer(guests_section):
        name = row.group(1).strip()
        if any(c.name == name for c in convives) or _fold(name) in _NOT_A_PERSON:
            continue
        guest = Convive(name=name, is_guest=True)
        guest.diet = _parse_diet(row.group(3))
        avoid = row.group(4)
        if "non documenté" not in avoid and "non documente" not in _fold(avoid):
            guest.forbidden = _split_list(avoid)
        convives.append(guest)

    return convives


# ── Contrôle de compatibilité ────────────────────────────────────────

def check_meal(description: str, convives: list[Convive]) -> list[Conflict]:
    """Un intitulé de plat + les convives présents → la liste des conflits.

    Volontairement basé sur les mots du libellé : c'est ce dont on dispose au
    moment de la planification, avant que la recette n'existe. Mieux vaut une
    alerte de trop qu'un plat que quelqu'un ne peut pas manger.
    """
    conflicts: list[Conflict] = []
    if not description:
        return conflicts
    folded = _fold(description)
    # « végétarienne » dans le libellé annule les implications de plat
    # (carbonara, bolognaise…) — pas les ingrédients explicites.
    veggie_declared = _VEGGIE_MARKER.search(folded) is not None

    for convive in convives:
        if convive.diet_waived_on(folded) is None:
            diet_terms = convive.diet_terms
        else:
            diet_terms = []
        for term in diet_terms:
            if veggie_declared and _fold(term) in MEAT_IMPLIED_DISHES:
                continue
            if _contains_term(folded, _fold(term)):
                conflicts.append(Conflict(convive.name, f"régime {convive.diet}", term))
                break  # une alerte par personne et par motif suffit
        for term in convive.forbidden:
            if _contains_term(folded, term):
                conflicts.append(Conflict(convive.name, "interdit", term))
                break
        for term in convive.dislikes:
            if _contains_term(folded, term):
                conflicts.append(Conflict(convive.name, "n'aime pas", term))
                break

    return conflicts


def check_ingredients(ingredients: list, convives: list[Convive]) -> list[Conflict]:
    """Ingrédients PARSÉS + convives présents → conflits, ligne par ligne.

    Complémentaire de `check_meal()`, pas concurrent : ce que le libellé d'un
    repas ne nomme pas, il ne peut pas le signaler. « Salade de haricots verts
    à la tomme de Savoie » ne dit pas qu'elle contient **six anchois** — muet
    pour un contrôle sur le titre, bloquant pour une végétarienne.

    L'appariement se fait sur `name_normalized` quand il existe : c'est la même
    clé que le garde-manger, déjà débarrassée des accents, des parenthèses et
    des ligatures (« bœuf » → « boeuf », qu'un ASCII naïf réduirait à « buf »).

    Le conflit porte le **libellé brut** de la ligne, pas le terme du régime :
    en cuisine on cherche « 8 tranches de lard fumé » dans la liste, pas « lard ».
    """
    conflicts: list[Conflict] = []
    if not ingredients:
        return conflicts

    rows: list[tuple[str, str]] = []
    for ing in ingredients:
        get = ing.get if isinstance(ing, dict) else lambda k, o=ing: getattr(o, k, None)
        folded = _fold(get("name_normalized") or get("name") or get("raw") or "")
        if folded:
            rows.append((folded, str(get("raw") or get("name") or "")))

    for convive in convives:
        seen: set[str] = set()
        checks = (
            [(t, f"régime {convive.diet}") for t in convive.diet_terms]
            + [(t, "interdit") for t in convive.forbidden]
            + [(t, "n'aime pas") for t in convive.dislikes]
        )
        for term, reason in checks:
            if reason in seen:
                continue
            is_diet = reason.startswith("régime ")
            for folded, raw in rows:
                if not _contains_term(folded, _fold(term)):
                    continue
                # Une exception dispense LA LIGNE, pas le régime : « quenelles de
                # veau » passe, le rôti de veau bloque toujours.
                if is_diet and convive.diet_waived_on(folded) is not None:
                    continue
                # Le terme sert à détecter, la ligne à retrouver l'ingrédient.
                conflicts.append(Conflict(convive.name, reason, raw or term))
                seen.add(reason)
                break
    return conflicts


def check_menu(meals: list[dict], convives: list[Convive]) -> dict[str, list[Conflict]]:
    """Menu complet → conflits par créneau, clé « jour/créneau »."""
    slots = ("breakfast", "lunch", "snack", "dinner")
    out: dict[str, list[Conflict]] = {}
    for meal in meals or []:
        day = meal.get("day", "?")
        for slot in slots:
            description = meal.get(slot)
            if not description:
                continue
            conflicts = check_meal(description, convives)
            if conflicts:
                out[f"{day}/{slot}"] = conflicts
    return out
