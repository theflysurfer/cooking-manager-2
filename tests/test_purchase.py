"""Unitaires — du besoin de recette à une quantité qu'un magasin comprend."""

from cooking_manager.pantry import Need
from cooking_manager.ingredients import normalize_name
from cooking_manager.purchase import (
    COUNTABLE,
    DOSE,
    MEASURED,
    Purchase,
    UNRESOLVED,
    purchase_for,
)


def need_of(name, qty=None, unit=None):
    return Need(name=name, name_normalized=normalize_name(name), qty=qty, unit=unit)


def bought(need, to_buy=None) -> Purchase:
    """Un achat attendu — l'absence d'achat est un cas testé à part."""
    result = purchase_for(need, to_buy)
    assert result is not None
    return result


class TestMeasured:
    def test_grams_pass_through(self):
        p = bought(need_of("champignons de Paris", 250.0, "g"))
        assert (p.kind, p.qty, p.unit) == (MEASURED, 250.0, "g")

    def test_millilitres_pass_through(self):
        p = bought(need_of("lait de coco", 400.0, "ml"))
        assert (p.kind, p.qty, p.unit) == (MEASURED, 400.0, "ml")


class TestCountable:
    def test_pieces_are_already_a_purchase(self):
        p = bought(need_of("pavés de saumon", 4.0, "pièce"))
        assert (p.kind, p.qty, p.unit) == (COUNTABLE, 4.0, "pièce")

    def test_a_fraction_rounds_up_never_down(self):
        """1,5 boîte de thon s'achète en 2 : arrondir vers le bas fait manquer."""
        p = bought(need_of("thon listao", 1.5, "boîte"))
        assert (p.kind, p.qty) == (COUNTABLE, 2.0)


class TestDose:
    def test_a_spoon_becomes_one_package(self):
        """« 2 c.s. de moutarde » → un pot, pas deux cuillères."""
        p = bought(need_of("moutarde", 2.0, "c.s."))
        assert (p.kind, p.qty, p.unit) == (DOSE, 1.0, "conditionnement")
        assert "2.0 c.s." in p.reason

    def test_garlic_cloves_are_a_dose_not_a_purchase(self):
        """On n'achète pas 21 gousses d'ail — on achète de l'ail."""
        p = bought(need_of("ail", 21.0, "gousse"))
        assert (p.kind, p.qty, p.unit) == (DOSE, 1.0, "conditionnement")

    def test_a_pinch_too(self):
        p = bought(need_of("curcuma", 1.0, "c.c."))
        assert p.kind == DOSE


class TestUnresolved:
    def test_no_unit_is_never_guessed(self):
        p = bought(need_of("carré de chocolat noir", 1.0, None))
        assert p.kind == UNRESOLVED
        assert p.qty is None

    def test_an_unknown_unit_is_declared_not_assumed(self):
        p = bought(need_of("quinoa", 2.0, "verre"))
        assert p.kind == UNRESOLVED
        assert "verre" in p.reason

    def test_no_quantity_at_all(self):
        p = bought(need_of("persil"))
        assert p.kind == UNRESOLVED


class TestUsesRemainingQuantity:
    def test_the_purchase_covers_what_is_missing_not_the_whole_need(self):
        """Le besoin est de 4 pavés, 2 sont en stock : on en achète 2."""
        p = bought(need_of("pavés de saumon", 4.0, "pièce"), to_buy=2.0)
        assert p.qty == 2.0

    def test_a_dose_stays_one_package_even_when_partly_in_stock(self):
        p = bought(need_of("moutarde", 4.0, "c.s."), to_buy=2.0)
        assert (p.kind, p.qty) == (DOSE, 1.0)


class TestNothingToBuy:
    def test_zero_to_buy_yields_no_purchase(self):
        assert purchase_for(need_of("riz", 300.0, "g"), to_buy=0.0) is None
