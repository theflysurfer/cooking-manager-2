"""Le contexte de la recette, pas le seul nom de la protéine, choisit le substitut."""

from cooking_manager.convives import Conflict
from cooking_manager.substitutions import (
    COOKING_METHOD_DOMINATIONS,
    COOKING_METHOD_KEYWORDS,
    CUISINE_KEYWORDS,
    PESCETARIAN_RULES,
    VOCABULARY_VERSION,
    RecipeContext,
    accommodations_by_evidence,
    concept_keys,
    load_vocabulary,
    detect_context,
    has_anchored_stew,
    is_accommodation_step,
    rule_applies,
    diets_at_table,
    find_substitution,
    repair_ingredients,
    unrepaired_conflicts,
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
        ["200 g de saucisson", "600 g de poulet", "200 g de lardons"],
        ("pescetarian",),
        detect_context("Mijoté à la cocotte"),
    )
    cibles = {r.substitution.source for r in repairs}
    assert cibles == {"poulet", "lardons"}


def test_un_regime_sans_table_ne_produit_rien():
    assert repair_ingredients(["600 g de poulet"], ("vegan",), RecipeContext()) == []


def test_un_ingredient_sans_regle_ne_produit_rien():
    """Le silence de `repairs` est légitime ici — c'est `unrepaired` qui le nomme."""
    repairs = repair_ingredients(["200 g de saucisson"], ("pescetarian",), RecipeContext())
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
    assert VOCABULARY_VERSION == "0.3.0"


def test_une_domination_ne_cite_que_des_cuissons_connues():
    known = concept_keys("cooking_methods")
    for method, dominated in COOKING_METHOD_DOMINATIONS.items():
        assert method in known
        assert dominated <= known, (
            f"« {method} » domine {sorted(dominated - known)}, absent du vocabulaire : "
            "la règle ne s'appliquerait jamais, sans erreur."
        )


def test_le_mijote_absorbe_le_rissolage_preparatoire():
    """SC-68 : « faites dorer » ouvre presque tout mijoté sans le rendre poêlé."""
    context = detect_context(
        "Blanquette de veau",
        steps=(
            "Faites dorer la viande dans une cocotte.",
            "Couvrir et laisser mijoter 40 min.",
        ),
    )
    assert "stew" in context.cooking_methods
    assert "pan-fried" not in context.cooking_methods


def test_une_vraie_poelee_reste_poelee():
    """Non-régression : sans mijoté détecté, la domination ne retire rien."""
    context = detect_context(
        "Filet de poulet poêlé",
        steps=("Faites dorer les filets à la poêle 6 min de chaque côté.",),
    )
    assert "pan-fried" in context.cooking_methods


def test_un_blocage_sans_regle_ressort_en_unrepaired_jamais_en_silence():
    """Le trou de couverture est nommé : `repairs` vide se lirait « rien à réparer »."""
    from cooking_manager.convives import Conflict

    conflicts = [Conflict("Clémence", "régime pescetarian", "200 g de saucisson")]
    unrepaired = unrepaired_conflicts(conflicts, repairs=[])
    assert len(unrepaired) == 1
    assert unrepaired[0].ingredient == "200 g de saucisson"
    assert unrepaired[0].diet == "pescetarian"
    assert "aucune règle" in unrepaired[0].reason


def test_un_blocage_repare_ne_ressort_pas_en_unrepaired():
    from cooking_manager.convives import Conflict

    line = "1,2 kg de poulet"
    repairs = repair_ingredients([line], ("pescetarian",))
    assert repairs, "le poulet doit avoir une règle"
    conflicts = [Conflict("Clémence", "régime pescetarian", line)]
    assert unrepaired_conflicts(conflicts, repairs) == []


def test_les_trois_regles_ancrees_sur_une_mesure_couvrent_leur_cas():
    """`magret`/`canard` viennent du corpus web, `bouillon de volaille` du vault."""
    for line in ("1 magret de canard", "500 ml eau ou bouillon de volaille"):
        assert find_substitution(line) is not None, f"« {line} » reste sans réparation"


def test_une_accommodation_en_probation_ne_passe_jamais_devant_une_active():
    ranking = accommodations_by_evidence()
    statuses = {c["key"]: c["status"] for c in load_vocabulary()["accommodations"]}
    seen_probation = False
    for key in ranking:
        if statuses[key] == "probation":
            seen_probation = True
        elif seen_probation:
            raise AssertionError(
                f"« {key} » est active mais classée après une accommodation en probation."
            )


def test_les_observations_survivent_a_la_generation():
    """`observed_in` s'arrêtait au YAML : tout tri par preuve aurait compté zéro partout."""
    observed = {
        c["key"]: c.get("observed_in")
        for c in load_vocabulary()["accommodations"]
    }
    assert observed["self_service"], "observed_in perdu à la génération de l'artefact."
    assert observed["separate_dish"] == []


MAFE_POULET_STEPS = (
    "Faire revenir les oignons dans l'huile 5 min. Ajouter l'ail, le concentré de tomate, cuire 2 min.",
    "Ajouter les patates douces et les aubergines. Couvrir, cuire 15 min à feu moyen.",
    "Poser les morceaux de poulet sur les légumes, couvrir. Cuire 12-15 min jusqu'à ce que le poulet soit cuit à coeur.",
    "Dans une petite poêle, saisir les crevettes 2-3 min de chaque côté. Les ajouter dans la part de Clémence au service.",
    "Cuire le riz à part. Servir le mafé sur un lit de riz.",
)


def test_le_mijote_sans_le_mot_est_detecte():
    assert has_anchored_stew(MAFE_POULET_STEPS)


def test_cuire_un_feculent_a_l_eau_bouillante_n_est_pas_un_mijote():
    assert not has_anchored_stew(
        (
            "Cuire le couscous perlé 10 min à l'eau bouillante salée, égoutter.",
            "Cuire les pommes de terre 20 min à l'eau bouillante salée.",
            "Cuire les lentilles 20 min à l'eau frémissante non salée.",
        )
    )


def test_une_etape_qui_sert_un_convive_nomme_est_une_accommodation():
    assert is_accommodation_step(MAFE_POULET_STEPS[3], ("Clémence",))


def test_un_prenom_ne_matche_pas_un_mot_qui_le_contient():
    assert not is_accommodation_step(
        "Râper les carottes en julienne.", ("Julien",)
    )


def test_le_libre_service_est_une_accommodation_sans_nom():
    assert is_accommodation_step("Disposer câpres et cornichons en libre-service.")
    assert is_accommodation_step("Laisser chacun garnir la sienne : thon, poivron.")


def test_cuire_a_part_n_est_pas_une_accommodation():
    assert not is_accommodation_step("Sauter les crevettes 3 min à part.", ("Clémence",))
    assert not is_accommodation_step("Cuire le riz à part.", ("Clémence",))


def test_l_etape_de_garniture_ne_pilote_plus_le_plat():
    context = detect_context(
        "Mafé au poulet",
        ingredients=("1,2 kg cuisses de poulet", "300 g crevettes décortiquées"),
        steps=MAFE_POULET_STEPS,
        convives=("Clémence",),
    )
    assert "stew" in context.cooking_methods
    assert "pan-seared" not in context.cooking_methods


def test_le_mafe_est_repare_en_cabillaud_pas_en_dorade():
    context = detect_context(
        "Mafé au poulet",
        ingredients=("1,2 kg cuisses de poulet", "350 g pâte d'arachide"),
        steps=MAFE_POULET_STEPS,
        convives=("Clémence",),
    )
    assert "west_african" in context.cuisines
    substitution = find_substitution("1,2 kg cuisses de poulet", context)
    assert substitution is not None
    assert substitution.target == "cabillaud"


def test_une_regle_de_cuisine_ne_deborde_pas_sur_une_autre_cuisine():
    ouest_africaine = next(
        r for r in PESCETARIAN_RULES if r.cuisines == ("west_african",) and r.target == "cabillaud"
    )
    assert rule_applies(ouest_africaine, RecipeContext(cuisines=("west_african",)))
    assert not rule_applies(ouest_africaine, RecipeContext(cuisines=("french", "italian")))


def test_une_regle_sans_cuisine_declaree_vaut_partout():
    universelle = next(r for r in PESCETARIAN_RULES if not r.cuisines)
    assert rule_applies(universelle, RecipeContext(cuisines=("french",)))
    assert rule_applies(universelle, RecipeContext())


def test_un_plat_sans_cuisine_detectee_ne_perd_aucune_regle():
    ouest_africaine = next(r for r in PESCETARIAN_RULES if r.cuisines == ("west_african",))
    assert rule_applies(ouest_africaine, RecipeContext())


def test_le_mafe_ne_deteint_pas_sur_un_poulet_en_cocotte_francais():
    context = detect_context(
        "Cocotte de poulet mijoté de ma grand-mère",
        ingredients=("1 poulet", "20 cl de vin blanc", "beurre", "crème fraîche"),
        steps=("Faire revenir les morceaux de poulet avec le beurre dans une cocotte.",),
    )
    assert "west_african" not in context.cuisines
    substitution = find_substitution("1 poulet fermier", context)
    assert substitution is not None
    assert "mafé" not in substitution.reason
