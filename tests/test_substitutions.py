"""Le contexte de la recette, pas le seul nom de la protéine, choisit le substitut."""

from cooking_manager.substitutions import (
    COOKING_METHOD_KEYWORDS,
    CUISINE_KEYWORDS,
    PESCETARIAN_RULES,
    RecipeContext,
    detect_context,
    find_substitution,
)


def test_detect_context_lit_les_accents():
    context = detect_context("Poulet rôti au four")
    assert "oven" in context.cooking_methods


def test_detect_context_croise_titre_et_ingredients():
    context = detect_context(
        "Curry de poulet",
        ingredients=("citronnelle", "lait de coco"),
        steps=("Laisser mijoter 20 min",),
    )
    assert "thai" in context.cuisines
    assert "stew" in context.cooking_methods


def test_meme_proteine_cuisson_differente_substitut_different():
    grille = find_substitution("poulet", detect_context("Poulet grillé au barbecue"))
    pane = find_substitution(
        "poulet", detect_context("Poulet pané, chapelure panko façon katsu")
    )
    assert grille is not None
    assert pane is not None
    assert grille.target == "thon"
    assert pane.target == "colin"
    assert grille.target != pane.target


def test_la_cuisine_departage_a_cuisson_egale():
    thai = find_substitution(
        "poulet", detect_context("Curry vert de poulet à la citronnelle, mijoté")
    )
    assert thai is not None
    assert thai.target == "lotte"
    assert "currys épicés" in thai.reason


def test_le_motif_et_la_regle_remontent_avec_le_resultat():
    result = find_substitution("poulet", detect_context("Poulet grillé"))
    assert result is not None
    assert result.reason
    assert result.rule.source == "poulet"
    assert 0.0 < result.confidence <= 1.0


def test_nom_compose_reconnu():
    result = find_substitution("blanc de poulet", detect_context("Poulet grillé"))
    assert result is not None
    assert result.rule.source == "poulet"


def test_charcuterie_traitee_piece_par_piece():
    lardons = find_substitution("lardons", detect_context("Faire revenir à la poêle"))
    assert lardons is not None
    assert lardons.target == "saumon fumé en dés"


def test_proteine_sans_regle_rend_none():
    assert find_substitution("tofu", detect_context("Tofu sauté au wok")) is None


def test_regime_sans_table_rend_none():
    assert find_substitution("poulet", RecipeContext(), diet="vegan") is None


def test_sans_contexte_la_priorite_de_base_decide():
    result = find_substitution("poulet", RecipeContext())
    assert result is not None
    assert result.target == "colin"
    assert result.rule.cooking_methods == ("breaded",)


def test_toutes_les_regles_ont_un_motif_et_une_priorite():
    for rule in PESCETARIAN_RULES:
        assert rule.reason.strip(), rule
        assert 0 < rule.priority <= 100, rule
        assert rule.source == rule.source.lower(), rule
        assert rule.target != rule.source, rule


def test_les_cles_de_contexte_des_regles_sont_toutes_connues():
    for rule in PESCETARIAN_RULES:
        for cuisine in rule.cuisines:
            assert cuisine in CUISINE_KEYWORDS, rule
        for method in rule.cooking_methods:
            assert method in COOKING_METHOD_KEYWORDS, rule
