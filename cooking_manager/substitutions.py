"""Substitution contextuelle d'une protéine incompatible, portée de cooking-manager v1."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from cooking_manager.convives import Conflict

DIET_REASON_PREFIX = "régime "


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

CUISINE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "asian": ("wok", "soja", "gingembre", "curry vert", "curry rouge", "coco",
              "citronnelle", "nuoc-mam"),
    "thai": ("curry vert", "curry rouge", "citronnelle", "coco", "piment thai",
             "basilic thai"),
    "chinese": ("wok", "soja", "gingembre", "cinq-epices", "nouilles chinoises"),
    "vietnamese": ("nuoc-mam", "pho", "banh", "nem", "citronnelle", "menthe fraiche"),
    "japanese": ("soja", "mirin", "sake", "wasabi", "teriyaki", "katsu", "tempura",
                 "panko", "gomasio", "japonais"),
    "indian": ("curry", "tandoori", "tikka", "masala", "garam masala", "cumin",
               "coriandre", "cardamome"),
    "pakistani": ("biryani", "karahi", "korma", "garam masala", "tandoori", "ghee"),
    "mediterranean": ("olive", "tomate", "basilic", "origan", "citron", "ail"),
    "greek": ("feta", "tzatziki", "kalamata", "yaourt grec", "origan", "aneth"),
    "spanish": ("chorizo", "pimenton", "paprika fume", "safran", "piquillo", "tapas"),
    "american": ("burger", "cheddar", "coleslaw", "buffalo", "cajun", "bbq sauce"),
    "french": ("vin blanc", "vin rouge", "echalote", "beurre", "creme fraiche",
               "moutarde"),
    "italian": ("tomate", "basilic", "parmesan", "mozzarella", "pesto"),
    "mexican": ("cumin", "piment", "avocat", "coriandre", "lime"),
    "middle_eastern": ("tahini", "cumin", "sumac", "grenade", "menthe"),
}

COOKING_METHOD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "grilled": ("grille", "barbecue", "plancha", "grill"),
    "pan-fried": ("poele", "saute", "a la poele", "dans une poele", "dans la poele",
                  "faites dorer"),
    "pan-seared": ("saisir", "snacke", "poeler"),
    "glazed": ("laque", "glace"),
    "oven": ("au four", "roti"),
    "stew": ("mijote", "ragout", "cocotte", "braise"),
    "breaded": ("pane", "chapelure", "panko", "katsu", "tempura"),
    "steamed": ("vapeur", "cuit a la vapeur"),
    "raw": ("tartare", "carpaccio", "cru", "marine"),
    "stir-fry": ("wok", "saute", "stir-fry"),
    "slow-cooked": ("mijote", "slow-cooked", "cuisson lente"),
    "smoked": ("fume", "au fumoir"),
    "bbq": ("barbecue", "bbq", "grill"),
}

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


def detect_context(
    name: str,
    description: str = "",
    ingredients: tuple[str, ...] = (),
    steps: tuple[str, ...] = (),
) -> RecipeContext:
    """Déduit cuisines et modes de cuisson du titre, du corps et des ingrédients."""
    haystack = fold(" ".join((name, description, *ingredients, *steps)))
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
    return RecipeContext(cuisines=cuisines, cooking_methods=methods)


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
    needle = fold(protein)
    candidates = [rule for rule in rules if fold(rule.source) in needle]
    if not candidates:
        return None
    best = max(candidates, key=lambda rule: score_rule(rule, resolved))
    return Substitution(
        source=best.source,
        target=best.target,
        reason=best.reason,
        confidence=min(score_rule(best, resolved) / 100, 1.0),
        rule=best,
    )


@dataclass(frozen=True)
class ConflictRepair:
    """Un conflit de régime et le remplacement qui le lève, pour qui il le lève."""

    matched: str
    diet: str
    convives: tuple[str, ...]
    substitution: Substitution


def repair_conflicts(
    conflicts: Sequence[Conflict],
    context: RecipeContext | None = None,
) -> list[ConflictRepair]:
    """Réparations proposées pour les conflits de RÉGIME — les aversions n'en relèvent pas."""
    concerned: dict[tuple[str, str], list[str]] = {}
    for conflict in conflicts:
        if not conflict.reason.startswith(DIET_REASON_PREFIX):
            continue
        diet = conflict.reason[len(DIET_REASON_PREFIX):].strip()
        concerned.setdefault((diet, conflict.matched), []).append(conflict.convive)

    repairs: list[ConflictRepair] = []
    for (diet, matched), convives in concerned.items():
        substitution = find_substitution(matched, context, diet=diet)
        if substitution is None:
            continue
        repairs.append(
            ConflictRepair(
                matched=matched,
                diet=diet,
                convives=tuple(convives),
                substitution=substitution,
            )
        )
    return repairs
