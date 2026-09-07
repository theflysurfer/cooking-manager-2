from cooking_manager.matching import Signals, compare


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
