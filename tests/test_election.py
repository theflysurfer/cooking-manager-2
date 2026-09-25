from cooking_manager.bans import Ban
from cooking_manager.election import (
    cut_words,
    ASK,
    ELECTED,
    MENU,
    OTHER_FOOD,
    OTHER_PACK,
    PACK_UNKNOWN,
    SUBSTITUTED,
    Offer,
    Wanted,
    elect,
)

CABILLAUD_MSC = Offer(name="Cabillaud msc 400 g", product_id="p1", offer_id="o1",
                      auchan_id="C1", brand="Pêche Océane")
CABILLAUD_BAS = Offer(name="Cabillaud prix bas 400 g", product_id="p2", offer_id="o2",
                      auchan_id="C2", brand="PRIX BAS")
CABILLAUD_AUTRE = Offer(name="Cabillaud pavé 400 g", product_id="p3", offer_id="o3",
                        auchan_id="C3", brand="Odyssée")
CABILLAUD_GROS = Offer(name="Cabillaud msc 1 kg", product_id="p4", offer_id="o4",
                       auchan_id="C4", brand="Pêche Océane")

BAN_PRIX_BAS = Ban(kind="brand", key="PRIX BAS", label="PRIX BAS",
                   reason="gamme refusée", scope="animal_protein")


def test_le_produit_voulu_disponible_est_elu_sans_substitution():
    result = elect(Wanted("Cabillaud msc 400 g", food="cabillaud", auchan_id="C1"),
                   [CABILLAUD_MSC, CABILLAUD_BAS], [])
    assert result.verdict == ELECTED
    assert result.origin == MENU
    assert result.offer is CABILLAUD_MSC


def test_le_produit_voulu_manquant_se_substitue_a_contenant_egal():
    result = elect(Wanted("Cabillaud msc 400 g", food="cabillaud", auchan_id="C1"),
                   [CABILLAUD_AUTRE], [])
    assert result.verdict == SUBSTITUTED
    assert result.origin == SUBSTITUTED
    assert result.offer is CABILLAUD_AUTRE
    assert "contenant équivalent" in result.reason


def test_sans_produit_nomme_une_election_n_est_pas_une_substitution():
    result = elect(Wanted("carotte", food="carotte", pack_size=1, pack_unit="kg"),
                   [Offer(name="Carottes france 1 kg", product_id="p", offer_id="o")], [])
    assert result.verdict == ELECTED
    assert result.origin == MENU
    assert "aucun produit nommé par la liste" in result.reason


def test_un_contenant_different_ne_se_substitue_jamais_en_silence():
    result = elect(Wanted("Cabillaud msc 400 g", food="cabillaud", auchan_id="C1"),
                   [CABILLAUD_GROS], [])
    assert result.verdict == ASK
    assert result.offer is None
    assert any(r["why"] == OTHER_PACK for r in result.rejected)


def test_une_gamme_bannie_ne_remplace_pas_et_la_question_la_nomme():
    result = elect(Wanted("Cabillaud msc 400 g", food="cabillaud", auchan_id="C1"),
                   [CABILLAUD_BAS], [BAN_PRIX_BAS])
    assert result.verdict == ASK
    assert "PRIX BAS" in (result.question or "")
    assert "Je saute, ou tu tranches ?" in (result.question or "")


def test_un_contenant_voulu_inconnu_ne_vaut_pas_contenant_quelconque():
    result = elect(Wanted("Cabillaud", food="cabillaud"), [CABILLAUD_AUTRE], [])
    assert result.verdict == ASK
    assert result.reason == PACK_UNKNOWN


def test_un_autre_aliment_est_ecarte_avec_son_motif():
    surimi = Offer(name="Surimi 400 g", product_id="p9", offer_id="o9", auchan_id="C9")
    result = elect(Wanted("Cabillaud msc 400 g", food="cabillaud", auchan_id="C1"), [surimi], [])
    assert result.verdict == ASK
    assert any(r["why"] == OTHER_FOOD for r in result.rejected)


def test_une_rupture_est_un_motif_de_rejet_pas_une_absence():
    rupture = Offer(name="Cabillaud pavé 400 g", product_id="p3", offer_id="o3",
                    auchan_id="C3", stock=0)
    result = elect(Wanted("Cabillaud msc 400 g", food="cabillaud", auchan_id="C1"), [rupture], [])
    assert result.verdict == ASK
    assert result.rejected[0]["why"] == "rupture"


POULET = [
    Offer(name="Filets de poulet jaune france 720 g", product_id="a", offer_id="a1"),
    Offer(name="Cuisses de poulet blanc france 720 g", product_id="b", offer_id="b1"),
    Offer(name="Hauts de cuisse de poulet blanc 720 g", product_id="c", offer_id="c1"),
]


def test_une_decoupe_de_poulet_reste_du_poulet():
    """7 produits sur 10 partaient en « autre aliment » le 2026-09-25 — #164."""
    for offer in POULET:
        result = elect(Wanted("poulet", food="poulet", pack_size=720, pack_unit="g"),
                       [offer], [])
        assert result.verdict == ELECTED, offer.name
        assert result.offer is offer


def test_un_complement_apres_l_aliment_nomme_un_autre_aliment():
    """« lait de coco » n'est pas du lait : la découpe s'ignore, pas le complément."""
    coco = Offer(name="Lait de coco 400 ml", product_id="d", offer_id="d1")
    result = elect(Wanted("lait", food="lait", pack_size=400, pack_unit="ml"), [coco], [])
    assert result.verdict == ASK
    assert any(r["why"] == OTHER_FOOD for r in result.rejected)


def test_un_plat_qui_cite_l_aliment_n_est_pas_l_aliment():
    """« bouillon de poulet » cite le poulet sans en être : « bouillon » n'est pas une découpe."""
    bouillon = Offer(name="Bouillon de poulet 720 g", product_id="e", offer_id="e1")
    result = elect(Wanted("poulet", food="poulet", pack_size=720, pack_unit="g"),
                   [bouillon], [])
    assert result.verdict == ASK
    assert any(r["why"] == OTHER_FOOD for r in result.rejected)


def test_l_aliment_dont_le_nom_porte_sa_decoupe_reste_apparie():
    """« filet de cabillaud » voulu, « filet de cabillaud » rendu : rien à promouvoir."""
    filet = Offer(name="Filet de cabillaud 400 g", product_id="f", offer_id="f1")
    result = elect(Wanted("filet de cabillaud", food="filet de cabillaud",
                          pack_size=400, pack_unit="g"), [filet], [])
    assert result.verdict == ELECTED


class TestCutsComeFromTheVocabulary:
    """La découpe est un axe FERMÉ du vocabulaire, jamais une table écrite dans le code."""

    def test_the_facet_feeds_the_cut_words(self):
        assert {"filet", "cuisse", "haut", "pilon", "aile", "roti"} <= cut_words()

    def test_a_facet_left_unread_would_not_read_as_no_cut(self):
        """Une facette vide ferait passer toute découpe pour un autre aliment."""
        assert cut_words(), "food_cuts absente de l'artefact épinglé — régénérer le vocabulaire"

    def test_a_cut_that_would_change_the_food_is_not_listed(self):
        """« blanc » est écarté : « blancs d'œufs » ne sont pas des œufs."""
        assert "blanc" not in cut_words()
