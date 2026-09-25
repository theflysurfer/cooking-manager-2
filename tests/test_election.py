from cooking_manager.bans import Ban
from cooking_manager.election import (
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
