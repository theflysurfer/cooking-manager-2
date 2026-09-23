"""Le cadre méditerranéen se dérive de l'aliment, et ne conclut pas sans lui — ADR 0033."""

import pytest

from cooking_manager.mediterranean import Criterion, cover, load_criteria
from cooking_manager.matching import clean_kind, food_kinds
from cooking_manager.nutrition import against_target

FISH = Criterion(key="oily-fish", code="5", label="Poisson gras",
                 satisfied_by=frozenset({"oily-fish"}))
WATER = Criterion(key="water-and-tea", code="9", label="Eau et thé",
                  satisfied_by=frozenset(), reason="hors de portée")


class TestCover:
    def test_un_jour_qui_porte_la_famille_tient_le_critere(self):
        read = cover({"2026-09-21": {"oily-fish", "vegetable"}}, [FISH])
        assert read["days"] == [{"day": "2026-09-21", "met": ["oily-fish"], "unmet": []}]
        assert read["criteria"][0]["days_met"] == 1

    def test_un_critere_hors_de_portee_n_est_ni_tenu_ni_manque(self):
        """Un critère qu'aucun ingrédient ne peut satisfaire ne doit pas faire baisser un score."""
        read = cover({"2026-09-21": {"oily-fish"}}, [FISH, WATER])
        assert [c["key"] for c in read["out_of_reach"]] == ["water-and-tea"]
        assert "water-and-tea" not in read["days"][0]["met"]
        assert "water-and-tea" not in read["days"][0]["unmet"]

    def test_sans_journee_aucun_critere_n_est_compte_manque(self):
        read = cover({}, [FISH])
        assert read["days"] == []
        assert read["criteria"][0] == {
            "key": "oily-fish", "code": "5", "label": "Poisson gras",
            "satisfied_by": ["oily-fish"], "days_met": 0, "days_total": 0}


class TestVocabulaire:
    def test_les_neuf_criteres_viennent_du_vocabulaire(self):
        assert [c.code for c in load_criteria()] == list("123456789")

    def test_chaque_axe_cite_une_famille_connue(self):
        kinds = set(food_kinds())
        for criterion in load_criteria():
            assert criterion.satisfied_by <= kinds

    def test_le_critere_hors_de_portee_dit_pourquoi(self):
        out = [c for c in load_criteria() if not c.in_reach]
        assert [c.code for c in out] == ["9"]
        assert out[0].reason

    def test_une_famille_inventee_est_refusee(self):
        assert clean_kind("oily-fish", "test") == "oily-fish"
        assert clean_kind(None, "test") is None
        with pytest.raises(ValueError, match="famille d'aliment"):
            clean_kind("poisson-gras", "test")


class TestCible:
    TARGET = {"kcal_min": 1800, "kcal_max": 1900,
              "protein_min": 180, "protein_max": 200,
              "carbs_min": None, "carbs_max": None,
              "fat_min": None, "fat_max": 90}

    def test_chaque_macro_est_situee_dans_sa_fourchette(self):
        verdict = against_target(
            {"kcal": 1850.0, "protein": 120.0, "fat": 95.0, "carbs": 130.0}, self.TARGET)
        assert verdict == {"kcal": "in_range", "protein": "under", "fat": "over"}

    def test_une_macro_sans_borne_ne_produit_aucun_verdict(self):
        assert "carbs" not in against_target({"carbs": 500.0}, self.TARGET)

    def test_une_macro_absente_ne_vaut_pas_zero(self):
        assert against_target({"kcal": None}, self.TARGET) == {}
