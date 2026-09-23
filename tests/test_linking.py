"""Chaque étage propose, un seul refuse — et le refus sait échouer (ADR 0032)."""

from cooking_manager.linking import (
    COMPOSITE_REFUSED,
    EXACT,
    QUEUED,
    group_by_candidate,
    link_counts,
    propose_food_key,
    propose_food_kind,
)
from cooking_manager.matching import facet_concepts

FOODS = {
    "pois chiche": "pois chiche",
    "saumon": "saumon",
    "lait": "lait demi-ecreme",
    "lait de coco": "lait de coco",
}


class TestEtageExact:
    def test_un_nom_identique_tranche_seul(self):
        p = propose_food_key("Pois chiches", FOODS)
        assert (p.decision, p.origin) == ("pois chiche", EXACT)

    def test_un_libelle_commercial_ne_tranche_pas_mais_propose(self):
        p = propose_food_key("auchan pois chiche 530g", FOODS)
        assert p.decision is None
        assert [c.value for c in p.candidates][:1] == ["pois chiche"]

    def test_le_premier_venu_n_est_jamais_elu(self):
        """Sans fiche « lait de coco », « lait » ne doit pas hériter du libellé."""
        p = propose_food_key("lait de coco", {"lait": "lait demi-ecreme"})
        assert p.decision is None
        assert [c.value for c in p.candidates] == ["lait"]


class TestEtageDeRefus:
    def test_un_libelle_sans_candidat_rend_none_et_se_nomme(self):
        p = propose_food_key("quaker cruesli chocolat noir 900g", FOODS)
        assert (p.decision, p.origin) == (None, QUEUED)
        assert p.candidates == ()
        assert p.reason

    def test_un_composite_n_est_jamais_rattache(self):
        p = propose_food_key("pois chiche", FOODS, nature="composite")
        assert p.decision is None
        assert p.reason == COMPOSITE_REFUSED

    def test_un_libelle_vide_ne_rend_pas_un_aliment(self):
        assert propose_food_key("   ", FOODS).decision is None


class TestFamilleDAliment:
    def test_un_rayon_qui_nomme_la_famille_tranche(self):
        p = propose_food_kind("courgette", "legumes", facet_concepts("food_kinds"))
        assert (p.decision, p.origin) == ("vegetable", EXACT)

    def test_une_famille_qui_en_domine_d_autres_ne_tranche_jamais(self):
        """« poisson » laisse gras/maigre ouvert : le trancher ferait mentir le critère 5."""
        p = propose_food_kind("saumon", "poissons", facet_concepts("food_kinds"))
        assert p.decision is None
        assert {c.value for c in p.candidates} >= {"oily-fish", "lean-fish"}

    def test_un_aliment_sans_rayon_connu_attend_au_lieu_de_se_dire_vide(self):
        p = propose_food_kind("levure chimique", None, facet_concepts("food_kinds"))
        assert (p.decision, p.origin) == (None, QUEUED)
        assert p.reason


class TestFile:
    def test_la_file_groupe_par_candidat_de_tete(self):
        entries = [
            {"ref": "a", "candidates": [{"value": "saumon"}]},
            {"ref": "b", "candidates": [{"value": "saumon"}]},
            {"ref": "c", "candidates": []},
        ]
        groups = group_by_candidate(entries)
        assert groups[0] == {"candidate": "saumon", "count": 2, "entries": entries[:2]}
        assert groups[1]["candidate"] is None

    def test_le_compte_en_attente_se_lit_avant_le_reste(self):
        assert link_counts(3, 7) == {"pending": 3, "settled": 7, "total": 10}
