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
