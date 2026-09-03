"""Substitution contextuelle d'une protéine incompatible, portée de cooking-manager v1."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Sequence
from functools import lru_cache
from dataclasses import dataclass
from importlib.resources import files

from cooking_manager.convives import Conflict

DIET_REASON_PREFIX = "régime "

VOCABULARY_FILE = "cooking-vocabulary.json"


def load_vocabulary() -> dict:
    """Le vocabulaire culinaire généré par ontology-manager, tiré et épinglé ici."""
    return json.loads(
        (files("cooking_manager") / VOCABULARY_FILE).read_text(encoding="utf-8")
    )


_VOCABULARY = load_vocabulary()
VOCABULARY_VERSION: str = _VOCABULARY["version"]


def _synonyms(facet: str) -> dict[str, tuple[str, ...]]:
    return {
        concept["key"]: tuple(concept["synonyms"])
        for concept in _VOCABULARY[facet]
        if concept["synonyms"]
    }


def _dominations(facet: str) -> dict[str, frozenset[str]]:
    return {
        concept["key"]: frozenset(concept.get("dominates") or ())
        for concept in _VOCABULARY[facet]
        if concept.get("dominates")
    }


def concept_keys(facet: str) -> frozenset[str]:
    """Toutes les clés déclarées pour une facette, quel que soit leur statut."""
    return frozenset(concept["key"] for concept in _VOCABULARY[facet])


_STATUS_RANK = {"active": 0, "probation": 1, "retired": 2}


def accommodations_by_evidence() -> tuple[str, ...]:
    """Les techniques d'accommodation, les mieux attestées d'abord.

    `status` est écrit dans le vocabulaire mais rien ne l'exécutait : une
    technique à zéro observation (`separate_dish`) pesait autant qu'une pratiquée
    quatre fois. Le rang classe d'abord par statut, puis par nombre
    d'observations — un consommateur qui propose dans cet ordre ne peut pas
    mettre une intuition devant une pratique mesurée.
    """
    return tuple(
        concept["key"]
        for concept in sorted(
            _VOCABULARY["accommodations"],
            key=lambda c: (
                _STATUS_RANK.get(c["status"], len(_STATUS_RANK)),
                -len(c.get("observed_in") or ()),
                c["key"],
            ),
        )
        if concept["status"] != "retired"
    )


@dataclass(frozen=True)
class SubstitutionRule:
    """Une règle de remplacement, avec le contexte culinaire où elle tient."""

    source: str
    target: str
    reason: str
    priority: int
    cuisines: tuple[str, ...] = ()
    cooking_methods: tuple[str, ...] = ()
    texture: str = ""
    budget: str = ""


PESCETARIAN_RULES: tuple[SubstitutionRule, ...] = (
    SubstitutionRule(
        source="poulet", target="cabillaud",
        cuisines=("west_african",),
        cooking_methods=("stew",), texture="firm", budget="medium",
        reason="Le mafé du foyer se fait déjà au cabillaud en gros morceaux, posé sur les légumes en fin de cuisson",
        priority=97,
    ),
    SubstitutionRule(
        source="poulet", target="lieu noir",
        cuisines=("west_african",),
        cooking_methods=("stew",), texture="firm", budget="low",
        reason="Alternative au cabillaud citée par la même fiche, tient dans la sauce arachide",
        priority=94,
    ),
    SubstitutionRule(
        source="poulet", target="cabillaud",
        cuisines=("asian", "thai", "chinese", "vietnamese"),
        cooking_methods=("stew", "steamed"), texture="firm", budget="medium",
        reason="Poisson blanc ferme, tient bien dans les currys et woks asiatiques",
        priority=90,
    ),
    SubstitutionRule(
        source="poulet", target="lotte",
        cuisines=("asian", "thai"),
        cooking_methods=("stew",), texture="firm", budget="high",
        reason="Texture proche du poulet, excellente dans les currys épicés",
        priority=95,
    ),
    SubstitutionRule(
        source="poulet", target="thon",
        cuisines=("asian", "japanese", "chinese"),
        cooking_methods=("pan-fried", "pan-seared"), texture="firm", budget="high",
        reason="Texture ferme, excellent poêlé aux sauces asiatiques",
        priority=92,
    ),
    SubstitutionRule(
        source="poulet", target="saumon",
        cuisines=("asian", "japanese"),
        cooking_methods=("pan-fried", "pan-seared"), texture="tender", budget="medium",
        reason="Chair grasse, excellent poêlé façon asiatique",
        priority=90,
    ),
    SubstitutionRule(
        source="poulet", target="thon",
        cuisines=("asian", "japanese", "chinese"),
        cooking_methods=("glazed",), texture="firm", budget="high",
        reason="Texture ferme, se laque parfaitement aux sauces sucrées asiatiques",
        priority=93,
    ),
    SubstitutionRule(
        source="poulet", target="saumon",
        cuisines=("asian", "japanese"),
        cooking_methods=("glazed",), texture="tender", budget="medium",
        reason="Chair grasse, absorbe bien les sauces laquées",
        priority=91,
    ),
    SubstitutionRule(
        source="poulet", target="cabillaud",
        cuisines=("indian", "pakistani"),
        cooking_methods=("stew", "oven", "grilled"), texture="firm", budget="medium",
        reason="Absorbe bien les épices, tient dans les currys et tandooris",
        priority=85,
    ),
    SubstitutionRule(
        source="poulet", target="saumon",
        cuisines=("indian",),
        cooking_methods=("grilled", "oven"), texture="firm", budget="high",
        reason="Riche en goût, excellent grillé façon tandoori",
        priority=80,
    ),
    SubstitutionRule(
        source="poulet", target="dorade",
        cuisines=("mediterranean", "greek", "italian"),
        cooking_methods=("grilled", "oven", "pan-fried"), texture="tender", budget="high",
        reason="Poisson méditerranéen classique, saveur douce et délicate",
        priority=90,
    ),
    SubstitutionRule(
        source="poulet", target="bar",
        cuisines=("mediterranean", "french"),
        cooking_methods=("grilled", "oven", "steamed"), texture="tender", budget="high",
        reason="Chair fine et savoureuse, parfait pour cuissons délicates",
        priority=85,
    ),
    SubstitutionRule(
        source="poulet", target="colin",
        cuisines=("french", "american", "japanese", "asian"),
        cooking_methods=("breaded",), texture="flaky", budget="low",
        reason="Se pane très bien, texture légère et floconneuse",
        priority=98,
    ),
    SubstitutionRule(
        source="poulet", target="sole",
        cuisines=("french", "japanese"),
        cooking_methods=("breaded",), texture="flaky", budget="high",
        reason="Texture délicate, panure croustillante garantie",
        priority=96,
    ),
    SubstitutionRule(
        source="poulet", target="thon",
        cooking_methods=("grilled", "pan-seared"), texture="firm", budget="high",
        reason="Texture de viande, tient parfaitement à la cuisson haute température",
        priority=95,
    ),
    SubstitutionRule(
        source="poulet", target="espadon",
        cooking_methods=("grilled",), texture="firm", budget="high",
        reason="Chair ferme et dense, excellent grillé",
        priority=90,
    ),
    SubstitutionRule(
        source="poulet", target="lotte",
        cooking_methods=("stew", "slow-cooked"), texture="firm", budget="high",
        reason="Ne se délite pas, texture proche du poulet en mijotage",
        priority=95,
    ),
    SubstitutionRule(
        source="poulet", target="lieu noir",
        cooking_methods=("stew", "oven"), texture="firm", budget="low",
        reason="Chair ferme, économique, polyvalent",
        priority=70,
    ),
    SubstitutionRule(
        source="poulet", target="cabillaud",
        cooking_methods=("pan-fried", "oven", "steamed"), texture="firm", budget="medium",
        reason="Poisson blanc polyvalent, s'adapte à toutes les cuissons",
        priority=60,
    ),
    SubstitutionRule(
        source="boeuf", target="thon",
        cuisines=("asian", "japanese"),
        cooking_methods=("pan-seared", "stir-fry", "raw"), texture="firm", budget="high",
        reason="Texture de viande rouge, excellent mi-cuit ou cru (tataki)",
        priority=95,
    ),
    SubstitutionRule(
        source="boeuf", target="espadon",
        cuisines=("asian",),
        cooking_methods=("grilled", "stir-fry"), texture="firm", budget="high",
        reason="Chair dense et ferme, tient au wok",
        priority=90,
    ),
    SubstitutionRule(
        source="boeuf", target="thon",
        cooking_methods=("grilled", "bbq"), texture="firm", budget="high",
        reason="Se cuit comme un steak, peut rester rosé au centre",
        priority=95,
    ),
    SubstitutionRule(
        source="boeuf", target="saumon",
        cooking_methods=("grilled", "bbq"), texture="firm", budget="medium",
        reason="Chair grasse qui ne dessèche pas, goût prononcé",
        priority=80,
    ),
    SubstitutionRule(
        source="boeuf", target="lotte",
        cooking_methods=("stew", "slow-cooked"), texture="firm", budget="high",
        reason="Texture ferme qui tient en mijotage, chair dense",
        priority=90,
    ),
    SubstitutionRule(
        source="boeuf", target="baudroie",
        cooking_methods=("stew",), texture="firm", budget="high",
        reason="Chair très ferme, ne se défait pas en cuisson longue",
        priority=85,
    ),
    SubstitutionRule(
        source="boeuf", target="thon", texture="firm", budget="high",
        reason="Alternative poisson la plus proche de la viande rouge",
        priority=60,
    ),
    SubstitutionRule(
        source="porc", target="saumon",
        cuisines=("asian", "chinese", "vietnamese"),
        cooking_methods=("pan-fried", "steamed", "grilled"), texture="tender", budget="medium",
        reason="Chair grasse qui rappelle le porc, goût prononcé",
        priority=90,
    ),
    SubstitutionRule(
        source="porc", target="saumon",
        cooking_methods=("grilled", "bbq"), texture="tender", budget="medium",
        reason="Chair grasse, tient bien à la grillade",
        priority=85,
    ),
    SubstitutionRule(
        source="porc", target="maquereau",
        cooking_methods=("grilled", "smoked"), texture="tender", budget="low",
        reason="Poisson gras au goût prononcé, excellent grillé",
        priority=80,
    ),
    SubstitutionRule(
        source="porc", target="saumon",
        cooking_methods=("stew", "slow-cooked"), texture="tender", budget="medium",
        reason="Chair grasse qui reste moelleuse en mijotage",
        priority=85,
    ),
    SubstitutionRule(
        source="porc", target="saumon", texture="tender", budget="medium",
        reason="Poisson gras polyvalent, texture moelleuse",
        priority=60,
    ),
    SubstitutionRule(
        source="chair à saucisse", target="saumon haché",
        cooking_methods=("pan-fried", "stew"), texture="tender", budget="medium",
        reason="Chair grasse, texture proche de la saucisse",
        priority=88,
    ),
    SubstitutionRule(
        source="saucisse de toulouse", target="darne de thon",
        cooking_methods=("grilled", "pan-fried"), texture="firm", budget="medium",
        reason="Chair ferme qui se tient bien, proche de la saucisse",
        priority=88,
    ),
    SubstitutionRule(
        source="lardons", target="saumon fumé en dés",
        cooking_methods=("pan-fried",), texture="crispy", budget="high",
        reason="Gras et fumé, même saveur intense que les lardons",
        priority=90,
    ),
    SubstitutionRule(
        source="lardons fumés", target="saumon fumé en dés",
        cooking_methods=("pan-fried",), texture="crispy", budget="high",
        reason="Gras et fumé, même saveur intense",
        priority=90,
    ),
    SubstitutionRule(
        source="chorizo", target="thon fumé en dés",
        cuisines=("spanish", "mediterranean", "french"),
        cooking_methods=("pan-fried", "stew"), texture="firm", budget="medium",
        reason="Saveur fumée et épicée, texture ferme",
        priority=88,
    ),
    SubstitutionRule(
        source="poitrine fumée", target="saumon fumé en tranches",
        cooking_methods=("pan-fried", "stew"), texture="tender", budget="high",
        reason="Gras et fumé, texture similaire aux tranches de poitrine",
        priority=90,
    ),
    SubstitutionRule(
        source="boulettes", target="boulettes de saumon",
        cooking_methods=("breaded", "pan-fried"), texture="tender", budget="medium",
        reason="Le saumon se façonne bien en boulettes",
        priority=85,
    ),
    SubstitutionRule(
        source="veau", target="sole",
        cooking_methods=("pan-fried", "breaded"), texture="tender", budget="high",
        reason="Chair délicate et tendre, cuisson rapide",
        priority=90,
    ),
    SubstitutionRule(
        source="veau", target="turbot",
        cooking_methods=("pan-fried", "oven"), texture="tender", budget="high",
        reason="Poisson noble à chair fine et délicate",
        priority=85,
    ),
    SubstitutionRule(
        source="veau", target="bar", texture="tender", budget="high",
        reason="Chair fine et savoureuse, cuisson délicate",
        priority=70,
    ),
    SubstitutionRule(
        source="agneau", target="saumon",
        cuisines=("mediterranean", "middle_eastern"),
        cooking_methods=("grilled", "oven"), texture="tender", budget="medium",
        reason="Goût prononcé, chair grasse, supporte les épices fortes",
        priority=90,
    ),
    SubstitutionRule(
        source="agneau", target="maquereau",
        cuisines=("mediterranean",),
        cooking_methods=("grilled",), texture="tender", budget="low",
        reason="Poisson au goût affirmé, tient aux épices",
        priority=80,
    ),
    SubstitutionRule(
        source="agneau", target="thon",
        cooking_methods=("grilled",), texture="firm", budget="high",
        reason="Chair ferme et goûteuse, excellent grillé",
        priority=75,
    ),
)

RULES_BY_DIET: dict[str, tuple[SubstitutionRule, ...]] = {
    "pescetarian": PESCETARIAN_RULES,
}

CUISINE_KEYWORDS: dict[str, tuple[str, ...]] = _synonyms("cuisines")

COOKING_METHOD_KEYWORDS: dict[str, tuple[str, ...]] = _synonyms("cooking_methods")

COOKING_METHOD_DOMINATIONS: dict[str, frozenset[str]] = _dominations("cooking_methods")

CUISINE_BONUS = 20
COOKING_METHOD_BONUS = 40


@dataclass(frozen=True)
class RecipeContext:
    """Cuisines et modes de cuisson détectés dans le texte d'une recette."""

    cuisines: tuple[str, ...] = ()
    cooking_methods: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        """Aucun indice de contexte n'a été trouvé."""
        return not self.cuisines and not self.cooking_methods


@dataclass(frozen=True)
class Substitution:
    """Le remplacement retenu, son motif, et la confiance du score."""

    source: str
    target: str
    reason: str
    confidence: float
    rule: SubstitutionRule


def fold(text: str) -> str:
    """Minuscules sans accents, pour comparer du texte de recette."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def keyword_pattern(keyword: str) -> re.Pattern[str]:
    """Le mot-clé en mot entier, deux lettres de flexion tolérées, pas davantage."""
    return re.compile(rf"(?<!\w){re.escape(fold(keyword))}\w{{0,2}}(?!\w)")


_CUISINE_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    cuisine: tuple(keyword_pattern(keyword) for keyword in keywords)
    for cuisine, keywords in CUISINE_KEYWORDS.items()
}

_COOKING_METHOD_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    method: tuple(keyword_pattern(keyword) for keyword in keywords)
    for method, keywords in COOKING_METHOD_KEYWORDS.items()
}

_SOURCE_PATTERNS: dict[str, re.Pattern[str]] = {
    rule.source: keyword_pattern(rule.source)
    for rules in RULES_BY_DIET.values()
    for rule in rules
}


ACCOMMODATION_MARKERS: tuple[str, ...] = ("libre-service", "libre service", "chacun")

_LIQUID_COOKING_PATTERN = re.compile(
    r"(?<!de)couvr|(?<!de)couvert|mijot|petits bouillons|pocher|fremiss"
)

_DURATION_PATTERN = re.compile(r"\d+\s*(?:-\s*\d+\s*)?min")


@lru_cache(maxsize=None)
def name_pattern(name: str) -> re.Pattern[str]:
    """Un prénom en mot entier STRICT — « Julien » ne doit pas matcher « julienne »."""
    return re.compile(rf"(?<!\w){re.escape(fold(name))}(?!\w)")


def is_accommodation_step(text: str, convives: Sequence[str] = ()) -> bool:
    """Une étape qui sert un convive nommé ou laisse chacun se servir ne décrit pas le plat."""
    folded = fold(text)
    if any(marker in folded for marker in ACCOMMODATION_MARKERS):
        return True
    return any(name_pattern(name).search(folded) for name in convives if name)


def has_anchored_stew(steps: Sequence[str]) -> bool:
    """Mijoté décrit sans le mot : milieu liquide ET durée ET protéine à remplacer nommée."""
    for step in steps:
        folded = fold(step)
        if not _LIQUID_COOKING_PATTERN.search(folded):
            continue
        if not _DURATION_PATTERN.search(folded):
            continue
        if any(pattern.search(folded) for pattern in _SOURCE_PATTERNS.values()):
            return True
    return False


def drop_dominated(methods: Sequence[str]) -> tuple[str, ...]:
    """La cuisson qui définit le plat efface celles qu'elle absorbe (SC-68).

    « Faites dorer » ouvre presque tout mijoté sans le rendre poêlé : sans cette
    passe, `pan-fried` pesait autant que `stew` dans une cocotte.
    """
    absorbed = {
        dominated
        for method in methods
        for dominated in COOKING_METHOD_DOMINATIONS.get(method, ())
    }
    return tuple(method for method in methods if method not in absorbed)


def detect_context(
    name: str,
    description: str = "",
    ingredients: tuple[str, ...] = (),
    steps: tuple[str, ...] = (),
    convives: Sequence[str] = (),
) -> RecipeContext:
    """Déduit cuisines et modes de cuisson du titre, du corps et des ingrédients."""
    dish_steps = tuple(
        step for step in steps if not is_accommodation_step(step, convives)
    )
    haystack = fold(" ".join((name, description, *ingredients, *dish_steps)))
    cuisines = tuple(
        cuisine
        for cuisine, patterns in _CUISINE_PATTERNS.items()
        if any(pattern.search(haystack) for pattern in patterns)
    )
    methods = tuple(
        method
        for method, patterns in _COOKING_METHOD_PATTERNS.items()
        if any(pattern.search(haystack) for pattern in patterns)
    )
    if "stew" not in methods and has_anchored_stew(dish_steps):
        methods = (*methods, "stew")
    return RecipeContext(cuisines=cuisines, cooking_methods=drop_dominated(methods))


def rule_applies(rule: SubstitutionRule, context: RecipeContext) -> bool:
    """Une règle qui déclare des cuisines ne vaut QUE dans ces cuisines, si le plat en nomme une."""
    if not rule.cuisines or not context.cuisines:
        return True
    return any(cuisine in context.cuisines for cuisine in rule.cuisines)


def score_rule(rule: SubstitutionRule, context: RecipeContext) -> int:
    """Priorité de base, plus un bonus par dimension de contexte effectivement appariée."""
    score = rule.priority
    if rule.cuisines and any(cuisine in context.cuisines for cuisine in rule.cuisines):
        score += CUISINE_BONUS
    if rule.cooking_methods and any(
        method in context.cooking_methods for method in rule.cooking_methods
    ):
        score += COOKING_METHOD_BONUS
    return score


def find_substitution(
    protein: str,
    context: RecipeContext | None = None,
    diet: str = "pescetarian",
) -> Substitution | None:
    """Meilleur remplacement pour cette protéine dans ce contexte, ou None si aucune règle."""
    rules = RULES_BY_DIET.get(diet)
    if not rules:
        return None
    resolved = context or RecipeContext()
    haystack = fold(protein)
    named = [rule for rule in rules if _SOURCE_PATTERNS[rule.source].search(haystack)]
    if not named:
        return None
    candidates = [rule for rule in named if rule_applies(rule, resolved)] or named
    best = max(candidates, key=lambda rule: score_rule(rule, resolved))
    return Substitution(
        source=best.source,
        target=best.target,
        reason=best.reason,
        confidence=min(score_rule(best, resolved) / 100, 1.0),
        rule=best,
    )


@dataclass(frozen=True)
class IngredientRepair:
    """La ligne d'ingrédient à remplacer, pour quel régime, et par quoi."""

    ingredient: str
    diet: str
    substitution: Substitution


def diets_at_table(conflicts: Sequence[Conflict]) -> tuple[str, ...]:
    """Les régimes qui ont réellement bloqué quelque chose, extraits des conflits."""
    diets: list[str] = []
    for conflict in conflicts:
        if not conflict.reason.startswith(DIET_REASON_PREFIX):
            continue
        diet = conflict.reason[len(DIET_REASON_PREFIX):].strip()
        if diet not in diets:
            diets.append(diet)
    return tuple(diets)


def repair_ingredients(
    ingredients: Sequence[str],
    diets: Sequence[str],
    context: RecipeContext | None = None,
) -> list[IngredientRepair]:
    """Balaie TOUTES les lignes d'ingrédients, pas seulement celles qu'un conflit a nommées."""
    repairs: list[IngredientRepair] = []
    seen: set[tuple[str, str]] = set()
    for diet in diets:
        if diet not in RULES_BY_DIET:
            continue
        for line in ingredients:
            if not line:
                continue
            substitution = find_substitution(line, context, diet=diet)
            if substitution is None:
                continue
            key = (diet, line)
            if key in seen:
                continue
            seen.add(key)
            repairs.append(
                IngredientRepair(ingredient=line, diet=diet, substitution=substitution)
            )
    return repairs
