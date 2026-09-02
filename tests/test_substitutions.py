"""Le contexte de la recette, pas le seul nom de la protéine, choisit le substitut."""

from cooking_manager.convives import Conflict
from cooking_manager.substitutions import (
    COOKING_METHOD_KEYWORDS,
    CUISINE_KEYWORDS,
    PESCETARIAN_RULES,
    VOCABULARY_VERSION,
    RecipeContext,
    concept_keys,
    detect_context,
    diets_at_table,
    find_substitution,
    repair_ingredients,
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


def test_un_mot_cle_ne_matche_pas_a_l_interieur_d_un_autre_mot():
    citronnelle = detect_context("Poulet grillé à la citronnelle")
    assert "mediterranean" not in citronnelle.cuisines
    cocotte = detect_context("Poulet en cocotte au vin blanc")
    assert "asian" not in cocotte.cuisines
    assert "french" in cocotte.cuisines


def test_la_flexion_du_mot_reste_toleree():
    assert "grilled" in detect_context("Brochettes grillées").cooking_methods
    assert "stew" in detect_context("Laisser mijoter 20 min").cooking_methods
    assert "mediterranean" in detect_context("Poulet au citron confit").cuisines


def test_la_collision_de_sous_chaine_changeait_le_substitut():
    result = find_substitution(
        "poulet", detect_context("Brochettes de poulet grillées à la citronnelle")
    )
    assert result is not None
    assert result.target == "thon"


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


def test_seuls_les_conflits_de_regime_ouvrent_une_reparation():
    conflicts = [
        Conflict("Clémence", "régime pescetarian", "600 g de blanc de poulet"),
        Conflict("Clémence", "n'aime pas", "mais"),
        Conflict("Léa", "interdit", "oeuf dur"),
    ]
    assert diets_at_table(conflicts) == ("pescetarian",)


def test_reparation_sur_la_ligne_d_ingredient_entiere():
    repairs = repair_ingredients(
        ["600 g de blanc de poulet", "2 oignons"],
        ("pescetarian",),
        detect_context("Poulet grillé au barbecue"),
    )
    assert len(repairs) == 1
    assert repairs[0].ingredient == "600 g de blanc de poulet"
    assert repairs[0].substitution.target == "thon"
    assert repairs[0].substitution.source == "poulet"


def test_toutes_les_lignes_carnees_sont_balayees_pas_seulement_la_premiere():
    repairs = repair_ingredients(
        ["500 ml de bouillon de volaille", "600 g de poulet", "200 g de lardons"],
        ("pescetarian",),
        detect_context("Mijoté à la cocotte"),
    )
    cibles = {r.substitution.source for r in repairs}
    assert cibles == {"poulet", "lardons"}


def test_un_regime_sans_table_ne_produit_rien():
    assert repair_ingredients(["600 g de poulet"], ("vegan",), RecipeContext()) == []


def test_un_ingredient_sans_regle_ne_produit_rien():
    repairs = repair_ingredients(
        ["500 ml de bouillon de volaille"], ("pescetarian",), RecipeContext()
    )
    assert repairs == []


def test_toutes_les_regles_ont_un_motif_et_une_priorite():
    for rule in PESCETARIAN_RULES:
        assert rule.reason.strip(), rule
        assert 0 < rule.priority <= 100, rule
        assert rule.source == rule.source.lower(), rule
        assert rule.target != rule.source, rule


def test_toute_cle_citee_existe_dans_le_vocabulaire():
    cuisines = concept_keys("cuisines")
    methods = concept_keys("cooking_methods")
    textures = concept_keys("textures")
    for rule in PESCETARIAN_RULES:
        for cuisine in rule.cuisines:
            assert cuisine in cuisines, rule
        for method in rule.cooking_methods:
            assert method in methods, rule
        if rule.texture:
            assert rule.texture in textures, rule


def test_toute_cle_citee_est_detectable():
    for rule in PESCETARIAN_RULES:
        for cuisine in rule.cuisines:
            assert CUISINE_KEYWORDS.get(cuisine), (
                f"{rule.source}→{rule.target} cite la cuisine « {cuisine} », "
                "qui n'a aucun synonyme dans le vocabulaire : son bonus ne peut jamais s'appliquer."
            )
        for method in rule.cooking_methods:
            assert COOKING_METHOD_KEYWORDS.get(method), (
                f"{rule.source}→{rule.target} cite la cuisson « {method} », sans synonyme."
            )


def test_le_vocabulaire_est_epingle():
    assert VOCABULARY_VERSION == "0.1.0"
