"""Unitaires — profils des convives et contrôle de compatibilité.

Tous ces tests dérivent d'un incident réel du 2026-08-04 : le menu programmait
des wraps au poulet un mardi midi alors que Clémence est pescétarienne, et
personne ne l'a vu. Le contrôle n'existait pas, et la table `convive` était vide.

Les faux positifs sont testés aussi durement que les faux négatifs : une alerte
qui se trompe finit par être ignorée, puis désactivée — et on se retrouve au
point de départ.
"""

from cooking_manager.convives import (
    Convive,
    _fold,
    check_ingredients,
    check_meal,
    check_menu,
    parse_convives,
)

VAULT_EXTRACT = """
## Famille (permanent)

### Julien
- **Poing** : 180g
- **Interdits absolus** :
  - ❌ Yaourt 0% MG
  - ❌ Riz blanc (riz complet OK)

### Clémence
- **Régime** : Pescétarien (pas de viande ni volaille, poisson OK)
- **Œufs** : accepte coque, brouillés — **refuse dur, poché, au plat, mollet**
- **N'aime pas** : maïs, céleri, endive

### Léa (bientôt 13 ans)
- **Œufs** : accepte coque, brouillés — **refuse dur, poché, omelette**
- **N'aime pas** : concombre, olives, maïs

## Invités récurrents

| Personne | Lien | Régime | À éviter |
|---|---|---|---|
| **Philippe** | père | Semi-végétarien (poulet 2x/sem) | Fenouil cuit |
| **Guillaume** | beau-père | Omnivore | **Ail, oignon blanc, tomates séchées** |

### Substituts saveurs (Guillaume)

| Au lieu de | Utiliser |
|---|---|
| Ail | Gingembre |
"""


class TestParsing:
    def setup_method(self):
        self.by_name = {c.name: c for c in parse_convives(VAULT_EXTRACT)}

    def test_diet_is_read(self):
        assert self.by_name["Clémence"].diet == "pescetarian"

    def test_semi_vegetarian_is_not_vegetarian(self):
        """« semi-végétarien » contient « végétarien ». Sans tri par longueur,
        Philippe passait pour végétarien strict et tout plat carné levait une
        fausse alerte."""
        assert self.by_name["Philippe"].diet == "semi-vegetarian"

    def test_dislikes_are_read(self):
        assert "mais" in self.by_name["Clémence"].dislikes

    def test_absolute_bans_are_read(self):
        assert any("riz blanc" in t for t in self.by_name["Julien"].forbidden)

    def test_egg_refusals_are_read(self):
        """Régression : les interdits ❌ écrasaient les refus d'œufs accumulés
        juste avant (réassignation au lieu d'un ajout)."""
        assert "oeuf dur" in self.by_name["Clémence"].forbidden
        assert "oeuf omelette" in self.by_name["Léa"].forbidden

    def test_julien_keeps_his_bans_despite_no_eggs_field(self):
        assert self.by_name["Julien"].forbidden

    def test_guests_are_parsed_from_their_table_only(self):
        """Régression : balayer TOUS les tableaux markdown faisait entrer
        « Maïs », « Mardi », « Ail »… dans le répertoire des convives."""
        names = set(self.by_name)
        assert "Guillaume" in names
        assert not {"Maïs", "Mardi", "Ail", "Aliment"} & names

    def test_guest_constraints(self):
        assert "ail" in self.by_name["Guillaume"].forbidden


class TestFolding:
    def test_oe_ligature_is_expanded(self):
        """⚠️ œ et æ n'ont AUCUNE décomposition Unicode : `encode('ascii')` les
        supprime. « œuf » devenait « uf », « bœuf » devenait « buf » — donc un
        interdit « oeuf dur » ne matchait jamais un plat écrit « œuf dur »."""
        assert _fold("œuf dur") == "oeuf dur"
        assert _fold("bœuf bourguignon") == "boeuf bourguignon"

    def test_accents_removed(self):
        assert _fold("Céleri rémoulade") == "celeri remoulade"


class TestCheckMeal:
    def setup_method(self):
        self.people = list(parse_convives(VAULT_EXTRACT).__iter__())
        self.by_name = {c.name: c for c in self.people}

    def test_chicken_conflicts_with_pescetarian(self):
        """LE cas fondateur."""
        conflicts = check_meal("Wraps hack poulet froid + crudités",
                               [self.by_name["Clémence"]])
        assert len(conflicts) == 1
        assert conflicts[0].convive == "Clémence"
        assert conflicts[0].matched == "poulet"

    def test_fish_is_fine_for_pescetarian(self):
        assert not check_meal("Saumon grillé + lentilles vertes",
                              [self.by_name["Clémence"]])

    def test_hard_egg_conflicts(self):
        """Salade niçoise : un second conflit réel du menu, jamais repéré à l'œil."""
        conflicts = check_meal("Salade niçoise (thon, œuf dur, haricots verts)",
                               [self.by_name["Clémence"], self.by_name["Léa"]])
        assert {c.convive for c in conflicts} == {"Clémence", "Léa"}

    def test_substring_is_not_a_match(self):
        """⚠️ « maïs » matchait dans « hou­mous **mais**on » : l'assiette froide
        du vendredi ressortait en conflit alors qu'elle ne contient pas de maïs.
        Un faux positif ruine la confiance autant qu'un faux négatif."""
        assert not check_meal("Assiette froide (crevettes, houmous maison, crudités)",
                              [self.by_name["Clémence"], self.by_name["Léa"]])

    def test_real_corn_is_still_caught(self):
        assert check_meal("Salade de maïs et thon", [self.by_name["Clémence"]])

    def test_semi_vegetarian_does_not_veto_chicken(self):
        """Un semi-végétarien mange du poulet — c'est une fréquence, pas un veto."""
        assert not check_meal("Poulet rôti", [self.by_name["Philippe"]])

    def test_absent_convive_raises_nothing(self):
        assert not check_meal("Wraps poulet", [self.by_name["Julien"]])

    def test_veggie_marker_cancels_dish_name_implication(self):
        """Faux positif réel du menu Bègles (refs #61) : « carbonara » implique
        la viande par son NOM, mais « végétarienne » dans le libellé annule
        l'implication — le plat est sans viande par déclaration."""
        assert not check_meal("Tagliatelles carbonara végétarienne",
                              [self.by_name["Clémence"]])

    def test_veggie_marker_keeps_explicit_ingredient_alert(self):
        """Le marqueur n'annule QUE l'implication de nom de plat : un ingrédient
        carné explicite continue d'alerter — mieux vaut une alerte de trop."""
        conflicts = check_meal("Burger végétarien au bacon",
                               [self.by_name["Clémence"]])
        assert len(conflicts) == 1
        assert conflicts[0].matched == "bacon"

    def test_plain_carbonara_still_alerts(self):
        """Sans marqueur, l'implication tient : une carbonara classique porte
        du guanciale/lardon même si le libellé ne les nomme pas."""
        conflicts = check_meal("Tagliatelles carbonara",
                               [self.by_name["Clémence"]])
        assert len(conflicts) == 1
        assert conflicts[0].matched == "carbonara"

    def test_empty_description_is_safe(self):
        assert check_meal("", self.people) == []


class TestCheckMenu:
    def test_reports_conflicts_by_slot(self):
        clemence = Convive(name="Clémence", diet="pescetarian")
        meals = [
            {"day": "mardi", "lunch": "Wraps poulet", "dinner": "Saumon grillé"},
            {"day": "mercredi", "lunch": "Salade lentilles"},
        ]
        result = check_menu(meals, [clemence])
        assert list(result) == ["mardi/lunch"]
        assert result["mardi/lunch"][0].matched == "poulet"


def _ing(raw, name_normalized):
    return {"raw": raw, "name": raw, "name_normalized": name_normalized}


class TestCheckIngredients:
    """Ce que le libellé d'un repas ne nomme pas, il ne peut pas le signaler."""

    # Salade de haricots verts à la tomme de Savoie, telle qu'imprimée.
    SALADE = [
        _ing("400 g de haricots verts frais", "haricots verts frais"),
        _ing("2 œufs extra-frais", "oeufs extra frais"),
        _ing("6 anchois à l'huile", "anchois a l huile"),
        _ing("60 g de tomme de Savoie", "tomme de savoie"),
    ]

    def test_catches_what_the_title_never_mentions(self):
        """« Salade de haricots verts à la tomme » ne dit pas qu'elle contient
        six anchois — muet au titre, bloquant pour une végétarienne."""
        veggie = Convive(name="Test", diet="vegetarian")
        assert check_meal("Salade de haricots verts à la tomme de Savoie", [veggie]) == []
        conflicts = check_ingredients(self.SALADE, [veggie])
        assert len(conflicts) == 1
        assert "anchois" in conflicts[0].matched

    def test_anchovies_do_not_block_a_pescetarian(self):
        """Le sur-blocage érode la confiance plus vite qu'un oubli : le poisson
        est compatible pescétarien et ne doit produire aucune alerte."""
        assert check_ingredients(self.SALADE, [Convive(name="C", diet="pescetarian")]) == []

    def test_conflict_carries_the_raw_line_not_the_diet_term(self):
        """En cuisine on cherche « 8 tranches de lard fumé » dans la liste,
        pas « lard »."""
        champignons = [_ing("8 tranches de lard fumé", "lard fume")]
        c = check_ingredients(champignons, [Convive(name="C", diet="pescetarian")])[0]
        assert c.matched == "8 tranches de lard fumé"

    def test_one_alert_per_person_and_per_reason(self):
        lots = [_ing("200 g de lard", "lard"), _ing("4 tranches de jambon", "jambon")]
        assert len(check_ingredients(lots, [Convive(name="C", diet="pescetarian")])) == 1

    def test_ligatures_survive_normalisation(self):
        """« bœuf » qu'un ASCII naïf réduirait à « buf » ne rencontrerait
        jamais le terme du régime."""
        boeuf = [_ing("500 g de bœuf haché", "boeuf hache")]
        assert check_ingredients(boeuf, [Convive(name="C", diet="vegetarian")])

    def test_tuna_rillettes_stay_compatible_for_a_pescetarian(self):
        """« rillettes » est volontairement absent de MEAT : celles du vault
        sont au THON. L'ajouter bloquerait une recette mangeable."""
        thon = [_ing("2 boîtes de rillettes de thon", "rillettes de thon")]
        assert check_ingredients(thon, [Convive(name="C", diet="pescetarian")]) == []

    def test_empty_is_safe(self):
        assert check_ingredients([], [Convive(name="C", diet="vegan")]) == []


class TestPluriels:
    """Les termes du régime sont au singulier, les recettes écrivent au pluriel."""

    def test_le_pluriel_bloque_comme_le_singulier(self):
        convive = Convive(name="C", diet="pescetarian")
        for line in ("200 g de lardons", "2 steaks hachés", "6 quenelles de veaux",
                     "4 saucissons secs", "3 tranches de jambons"):
            assert check_ingredients([_ing(line, line)], [convive]), (
                f"« {line} » doit bloquer un pescétarien"
            )

    def test_le_pluriel_interne_d_une_expression_est_tolere(self):
        """« oeuf dur » doit rencontrer « 2 oeufs durs » — les DEUX mots fléchissent."""
        convive = Convive(name="C", diet="standard", dislikes=["oeuf dur"])
        for line in ("1 oeuf dur", "2 oeufs durs"):
            assert check_ingredients([_ing(line, line)], [convive]), f"« {line} »"

    def test_une_exception_se_declare_au_singulier_et_couvre_le_pluriel(self):
        convive = Convive(
            name="Clémence", diet="pescetarian", diet_exceptions=["quenelle de veau"],
        )
        for line in ("1 quenelle de veau", "6 quenelles de veau"):
            assert check_ingredients([_ing(line, line)], [convive]) == [], f"« {line} »"

    def test_le_pluriel_ne_rouvre_pas_le_faux_positif_maison(self):
        """« maïs » ne doit toujours pas matcher « houmous maison »."""
        convive = Convive(name="C", diet="standard", dislikes=["mais"])
        assert check_ingredients([_ing("houmous maison", "houmous maison")], [convive]) == []
        assert check_ingredients([_ing("200 g de mais", "mais")], [convive])


class TestDietExceptions:
    """Un régime n'est pas un absolu : Clémence est pescétarienne ET mange du boudin."""

    def test_une_exception_leve_le_blocage(self):
        stricte = Convive(name="Clémence", diet="pescetarian")
        tolerante = Convive(name="Clémence", diet="pescetarian", diet_exceptions=["boudin"])
        plat = [_ing("300 g de boudin noir", "boudin noir")]
        assert check_ingredients(plat, [stricte]), "sans exception, le boudin doit bloquer"
        assert check_ingredients(plat, [tolerante]) == []

    def test_une_exception_ne_leve_que_le_terme_nomme(self):
        tolerante = Convive(name="Clémence", diet="pescetarian", diet_exceptions=["boudin"])
        conflicts = check_ingredients([_ing("600 g de poulet", "poulet")], [tolerante])
        assert [c.matched for c in conflicts] == ["600 g de poulet"]

    def test_une_exception_porte_sur_la_preparation_pas_sur_la_viande(self):
        """« quenelles de veau » se mange, le rôti de veau non — même terme bloquant."""
        convive = Convive(
            name="Clémence", diet="pescetarian",
            diet_exceptions=["quenelle de veau"],
        )
        quenelles = [_ing("6 quenelles de veau", "quenelles de veau")]
        roti = [_ing("1,2 kg de rôti de veau", "rôti de veau")]
        assert check_ingredients(quenelles, [convive]) == []
        assert check_ingredients(roti, [convive]), "le rôti de veau doit bloquer"

    def test_une_exception_ne_dispense_que_sa_ligne(self):
        convive = Convive(
            name="Clémence", diet="pescetarian",
            diet_exceptions=["quenelle de veau"],
        )
        plat = [
            _ing("6 quenelles de veau", "quenelles de veau"),
            _ing("200 g de lardons", "lardons"),
        ]
        conflicts = check_ingredients(plat, [convive])
        assert [c.matched for c in conflicts] == ["200 g de lardons"]

    def test_une_exception_ne_touche_pas_les_interdits_personnels(self):
        """`forbidden` est une contrainte propre, pas une clause du régime."""
        convive = Convive(
            name="Clémence", diet="pescetarian",
            forbidden=["oeuf dur"], diet_exceptions=["oeuf dur"],
        )
        conflicts = check_ingredients([_ing("2 oeufs durs", "oeuf dur")], [convive])
        assert [c.reason for c in conflicts] == ["interdit"]
