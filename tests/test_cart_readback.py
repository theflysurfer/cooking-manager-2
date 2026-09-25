from backend.auchan import cart_lines, count_for
from cooking_manager.election import Offer

OFFER = Offer(name="Cabillaud msc 400 g", product_id="p1", offer_id="o1", auchan_id="C1")


def test_les_lignes_se_lisent_quel_que_soit_le_nom_du_champ():
    assert cart_lines({"items": [{"offer_id": "o1"}]}) == [{"offer_id": "o1"}]
    assert cart_lines({"lines": [{"offerId": "o1"}]}) == [{"offerId": "o1"}]


def test_un_panier_sans_la_ligne_rend_zero_pas_une_erreur():
    assert count_for({"lines": []}, OFFER) == 0


def test_la_quantite_se_lit_par_offre_meme_en_camel_case():
    cart = {"lines": [{"offerId": "o1", "quantity": 3}]}
    assert count_for(cart, OFFER) == 3


def test_une_autre_ligne_ne_compte_pas_pour_celle_ci():
    cart = {"lines": [{"offerId": "autre", "quantity": 6}]}
    assert count_for(cart, OFFER) == 0
