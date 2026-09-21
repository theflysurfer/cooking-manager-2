import pytest

from cooking_manager.matching import (
    Signals,
    clean_nature,
    compare,
    link_food_key,
    product_natures,
    strip_brand,
)


def sig(name, grams=None, price=None, brand=None):
    return Signals(name=name, grams=grams, price_per_kg=price, brand=brand)


class TestRefutation:
    def test_weight_refutes(self):
        """Un pot de 10 g et un sachet de 500 g ne sont pas le même usage."""
        m = compare(sig("origan", grams=10), sig("origan", grams=500))
        assert m.verdict == "refuse"
        assert any("poids" in r for r in m.reasons)

    def test_price_refutes_on_an_order_of_magnitude(self):
        m = compare(sig("curcuma", price=34.0), sig("safran", price=3000.0))
        assert m.verdict == "refuse"

    def test_a_different_brand_never_refutes_the_food(self):
        m = compare(sig("comté", brand="Juraflore"), sig("comté", brand="Entremont"))
        assert m.verdict == "propose"


class TestMuteSignals:
    def test_a_zero_price_is_mute_not_favourable(self):
        """`price` vaut 0.0 dans les résultats Auchan : un parsing manqué."""
        m = compare(sig("origan", price=0.0), sig("origan", price=42.0))
        assert m.verdict == "unsure"
        assert any("prix" in r for r in m.reasons)

    def test_a_missing_weight_does_not_refute(self):
        assert compare(sig("comté"), sig("comté", grams=250)).verdict == "propose"


class TestNameAlone:
    def test_different_names_never_propose(self):
        assert compare(sig("riz"), sig("vinaigre de riz")).verdict == "refuse"

    def test_a_qualifier_still_concords(self):
        assert compare(sig("origan"), sig("origan séché")).verdict == "propose"


FOODS = {"oeuf": "Oeufs", "pain complet": "Pain complet"}


class TestLinkingRatchet:
    """Un single dont le nom désigne l'aliment est rattaché — refs #90, #100."""

    def test_a_single_whose_name_designates_the_food_is_linked(self):
        assert link_food_key(sig("oeufs x12"), "single", FOODS) == "oeuf"

    def test_a_single_without_a_matching_food_stays_unlinked(self):
        assert link_food_key(sig("pignon de pin"), "single", FOODS) is None

    def test_a_qualifier_before_the_food_blocks_the_link(self):
        """Marque retirée, le mot de tête reste « bio » : ça ne désigne pas l'aliment."""
        assert link_food_key(sig("bio plein air oeufs x12"), "single", FOODS) is None

    def test_a_nature_left_unknown_still_links(self):
        """Seul `composite` bloque : une nature absente ne vaut pas refus."""
        assert link_food_key(sig("oeufs x12"), None, FOODS) == "oeuf"


class TestCompositeIsNeverLinked:
    """Un plat rattaché à un ingrédient prend ses macros et se lit comme réparé — ADR 0016."""

    def test_a_composite_is_not_linked_even_when_the_name_matches(self):
        assert link_food_key(sig("oeufs x12"), "composite", FOODS) is None

    def test_the_name_alone_would_have_proposed(self):
        """Le refus vient de la nature, pas d'un désaccord de noms."""
        assert compare(sig("oeufs x12"), sig("Oeufs")).verdict == "propose"


class TestProductNature:
    def test_the_vocabulary_carries_the_two_natures(self):
        assert product_natures() == ("single", "composite")

    def test_an_invented_nature_is_refused(self):
        with pytest.raises(ValueError):
            clean_nature("plat", "fiche.md")

    def test_an_absent_nature_stays_absent(self):
        assert clean_nature(None) is None
        assert clean_nature("null") is None

    def test_a_declared_nature_is_kept(self):
        assert clean_nature("single") == "single"


class TestBrandInTheName:
    def test_a_leading_brand_is_removed(self):
        assert strip_brand("Auchan Pignons de Pin", "Auchan") == "pignon de pin"

    def test_a_name_reduced_to_its_brand_is_kept(self):
        assert strip_brand("Auchan", "Auchan") == "Auchan"
