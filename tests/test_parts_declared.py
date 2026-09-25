"""#159 — une part de convive est une donnée, pas une parenthèse."""

import pytest

from cooking_manager.parts import (
    DeclaredPart,
    declared_parts,
    lines_for_person,
    undeclared_part,
)


def ing(position, name, **kw):
    base = {"position": position, "name": name, "raw": kw.pop("raw", name),
            "for_person_id": None, "replaces_position": None}
    base.update(kw)
    return base


RISOTTO = [
    ing(1, "poulet fermier", raw="480 g poulet fermier"),
    ing(2, "crevettes", raw="150 g crevettes décortiquées", for_person_id=3,
        replaces_position=1),
    ing(3, "riz arborio", raw="300 g riz arborio"),
]


class TestDeclaredParts:
    def test_une_ligne_sans_convive_n_est_pas_une_part(self):
        assert declared_parts([ing(1, "poulet")]) == []

    def test_la_part_porte_son_convive_et_la_ligne_qu_elle_remplace(self):
        parts = declared_parts(RISOTTO)
        assert parts == [DeclaredPart(person_id=3, position=2, replaces_position=1,
                                      raw="150 g crevettes décortiquées")]

    def test_une_part_sans_replaces_position_reste_une_part(self):
        parts = declared_parts([ing(1, "tofu", for_person_id=3)])
        assert parts[0].replaces_position is None

    def test_le_texte_ne_declare_rien_sans_la_donnee(self):
        assert declared_parts([ing(1, "crevettes", raw="150 g crevettes (part de Clémence)")]) == []


class TestLinesForPerson:
    def test_un_convive_sans_part_voit_tout_le_plat_sauf_les_parts_des_autres(self):
        lines = lines_for_person(RISOTTO, person_id=5)
        assert [line["position"] for line in lines] == [1, 3]

    def test_le_convive_de_la_part_ne_voit_pas_la_ligne_remplacee(self):
        lines = lines_for_person(RISOTTO, person_id=3)
        assert [line["position"] for line in lines] == [2, 3]

    def test_un_person_id_inconnu_est_traite_comme_un_convive_sans_part(self):
        assert [line["position"] for line in lines_for_person(RISOTTO, person_id=None)] == [1, 3]

    def test_une_part_sans_replaces_position_s_ajoute_sans_rien_retirer(self):
        lines = [ing(1, "poulet"), ing(2, "tofu", for_person_id=3)]
        assert [line["position"] for line in lines_for_person(lines, 3)] == [1, 2]

    def test_deux_parts_pour_deux_convives_ne_se_melangent_pas(self):
        lines = [ing(1, "boeuf"),
                 ing(2, "pois chiches", for_person_id=3, replaces_position=1),
                 ing(3, "saumon", for_person_id=2, replaces_position=1)]
        assert [line["position"] for line in lines_for_person(lines, 3)] == [2]
        assert [line["position"] for line in lines_for_person(lines, 2)] == [3]
        assert [line["position"] for line in lines_for_person(lines, 5)] == [1]


NAMES = {"Clémence": 3, "Léa": 9, "Béatrice": 2}


class TestUndeclaredPart:
    @pytest.mark.parametrize("raw", [
        "150 g crevettes décortiquées (part Clémence)",
        "150 g pois chiches cuits, égouttés (part de Clémence)",
        "200 g haricots rouges égouttés (Part De Clemence)",
        "1 kg concombre (servi à part pour Léa)",
    ])
    def test_un_texte_de_part_sans_donnee_est_signale(self, raw):
        assert undeclared_part(raw, None, NAMES) is not None

    def test_le_meme_texte_avec_sa_donnee_ne_leve_rien(self):
        raw = "150 g crevettes (part de Clémence)"
        assert undeclared_part(raw, 3, NAMES) is None

    @pytest.mark.parametrize("raw", [
        "1 concombre — servi à part, jamais mêlé au taboulé",
        "6 pilons ou cuisses de poulet (pour 3 parts carnées)",
        "300 g riz arborio",
        "1 part de tarte",
    ])
    def test_une_part_qui_ne_nomme_personne_n_est_pas_une_part_de_convive(self, raw):
        assert undeclared_part(raw, None, NAMES) is None

    def test_un_prenom_inconnu_du_referentiel_ne_leve_rien(self):
        assert undeclared_part("150 g tofu (part de Gaspard)", None, NAMES) is None

    def test_le_motif_nomme_le_convive_et_ce_qui_manque(self):
        motif = undeclared_part("150 g crevettes (part de Clémence)", None, NAMES)
        assert motif and "for_person_id" in motif and "Clémence" in motif


class TestCheckIngredientsSuitLesParts:
    """Le cœur de #159 : une part déclarée cesse de compter la viande contre son convive."""

    def _clemence(self):
        from cooking_manager.convives import Convive
        return Convive(name="Clémence", diet="pescetarian")

    def test_sans_part_la_viande_compte_contre_la_pescetarienne(self):
        from cooking_manager.convives import check_ingredients
        lines = [ing(1, "poulet fermier", raw="480 g poulet fermier")]
        assert check_ingredients(lines, [self._clemence()], person_ids={"Clémence": 3})

    def test_avec_sa_part_la_viande_ne_compte_plus_contre_elle(self):
        from cooking_manager.convives import check_ingredients
        assert check_ingredients(RISOTTO, [self._clemence()],
                                 person_ids={"Clémence": 3}) == []

    def test_la_part_d_un_AUTRE_convive_ne_la_couvre_pas(self):
        from cooking_manager.convives import check_ingredients
        lines = [ing(1, "poulet fermier", raw="480 g poulet fermier"),
                 ing(2, "crevettes", for_person_id=2, replaces_position=1)]
        assert check_ingredients(lines, [self._clemence()], person_ids={"Clémence": 3})

    def test_sans_person_ids_le_comportement_historique_est_conserve(self):
        from cooking_manager.convives import check_ingredients
        assert check_ingredients(RISOTTO, [self._clemence()])
