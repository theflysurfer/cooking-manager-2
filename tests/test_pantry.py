"""Unitaires du garde-manger : un faux positif coûte plus cher qu'un faux négatif."""

from datetime import date, timedelta

import pytest

from cooking_manager.pantry import (
    ENOUGH,
    MISSING,
    PARTIAL,
    STATUS_OK,
    STATUS_OUT,
    UNKNOWN,
    Need,
    Pantry,
    PantryItem,
    build_needs,
    check_need,
    parse_pantry,
)
from cooking_manager.ingredients import Ingredient, normalize_name

VAULT = """---
updated: 2026-07-11
---

# Garde-manger

## Épicerie sèche

- Miel bio (liquide) — 2 pots (entré 2026-06-02) # status=ok
- Sauce soja salée (Auchan) — 1 flacon 250 ml # status=ok
- Farine T65 — 250 g # status=low
- Riz basmati — 0 # status=out

## Frais — Protéines

- Œufs — 6 pièces (entré 2026-07-08) # status=ok
- Filets de poulet — 480 g / 4 filets # status=urgent
"""


def need_of(name, qty=None, unit=None):
    """Un besoin isolé, tel que `build_needs` le produirait."""
    return Need(name=name, name_normalized=normalize_name(name), qty=qty, unit=unit)


@pytest.fixture
def pantry():
    return parse_pantry(VAULT)


class TestParse:
    def test_reads_updated_and_rayons(self, pantry):
        assert pantry.updated == date(2026, 7, 11)
        assert {i.rayon for i in pantry.items} == {"Épicerie sèche", "Frais — Protéines"}

    def test_reads_status_and_quantities(self, pantry):
        farine = pantry.find("farine")
        assert farine is not None
        assert (farine.status, farine.qty_value, farine.unit) == ("low", 250.0, "g")

    def test_ligature_in_name_is_matchable(self, pantry):
        """Sans expansion explicite de la ligature, « oeuf dur » ne trouve jamais « Œufs »."""
        assert pantry.find("oeufs") is not None

    def test_staleness_is_computed_not_assumed(self, pantry):
        assert pantry.age_days(today=date(2026, 8, 4)) == 24
        assert pantry.is_stale(today=date(2026, 8, 4)) is True
        assert pantry.is_stale(today=date(2026, 7, 12)) is False


class TestMatching:
    def test_containment_match(self, pantry):
        """« miel » doit rencontrer « Miel bio (liquide) », sinon on rachète du miel."""
        item = pantry.find("miel")
        assert item is not None and item.status == "ok"

    def test_no_match_returns_none(self, pantry):
        assert pantry.find("cardamome") is None

    def test_partial_word_does_not_match(self, pantry):
        """« ri » ne doit pas matcher « riz » : une inclusion nue fabrique des faux positifs."""
        assert pantry.find("ri") is None


class TestVerdicts:
    def test_enough_when_stock_covers(self, pantry):
        need = need_of("miel", 1.0, "c.s.")
        assert check_need(need, pantry).outcome == ENOUGH

    def test_missing_when_absent(self, pantry):
        need = need_of("cardamome", 200.0, "g")
        v = check_need(need, pantry)
        assert v.outcome == MISSING and v.pantry_item is None

    def test_missing_when_status_out(self, pantry):
        need = need_of("riz basmati", 300.0, "g")
        assert check_need(need, pantry).outcome == MISSING

    def test_partial_when_stock_is_short(self, pantry):
        need = need_of("farine T65", 500.0, "g")
        v = check_need(need, pantry)
        assert v.outcome == PARTIAL
        assert v.to_buy == 250.0

    def test_unknown_when_units_are_incommensurable(self, pantry):
        """« 3 filets » contre « 480 g » : on ne convertit pas, on demande."""
        need = need_of("filets de poulet", 3.0, "pièce")
        assert check_need(need, pantry).outcome == UNKNOWN

    def test_quantityless_need_on_stocked_item_is_enough(self, pantry):
        """Sans quantité chiffrée sur un article en stock, `inconnu` noierait la liste."""
        need = need_of("sauce soja")
        assert check_need(need, pantry).outcome == ENOUGH


class TestStaleness:
    def test_fresh_is_assumed_gone_when_inventory_is_old(self, pantry):
        """Frais + inventaire vieux de 24 jours → supposé épuisé, et la déduction est DITE."""
        need = need_of("œufs", 4.0, "pièce")
        v = check_need(need, pantry, today=date(2026, 8, 4))
        assert v.outcome in (MISSING, UNKNOWN)
        assert "inventaire" in v.reason.lower()

    def test_dry_goods_survive_a_stale_inventory(self, pantry):
        """Le sec ne périme pas : la règle d'ancienneté ne s'y applique pas."""
        need = need_of("miel", 1.0, "c.s.")
        assert check_need(need, pantry, today=date(2026, 8, 4)).outcome == ENOUGH

    def test_fresh_is_trusted_when_inventory_is_recent(self, pantry):
        need = need_of("œufs", 4.0, "pièce")
        assert check_need(need, pantry, today=date(2026, 7, 12)).outcome == ENOUGH


class TestAggregation:
    def test_same_ingredient_across_recipes_is_summed(self):
        """Deux recettes qui veulent des œufs produisent UNE ligne, sinon on achète deux fois."""
        needs = build_needs([
            ("Gratin", [Ingredient(raw="2 œufs", name="œufs", qty_min=2.0, unit="pièce", position=1)], 1.0),
            ("Cookies", [Ingredient(raw="3 œufs", name="œufs", qty_min=3.0, unit="pièce", position=1)], 1.0),
        ])
        assert len(needs) == 1
        assert needs[0].qty == 5.0
        assert set(needs[0].recipes) == {"Gratin", "Cookies"}

    def test_portions_ratio_scales_quantities(self):
        needs = build_needs([
            ("Gratin", [Ingredient(raw="400 g pommes de terre", name="pommes de terre",
                                   qty_min=400.0, unit="g", position=1)], 1.5),
        ])
        assert needs[0].qty == 600.0

    def test_incommensurable_units_stay_separate(self):
        """« 2 pièces » et « 200 g » ne s'additionnent pas : le total serait faux et crédible."""
        needs = build_needs([
            ("A", [Ingredient(raw="2 courgettes", name="courgettes", qty_min=2.0, unit="pièce", position=1)], 1.0),
            ("B", [Ingredient(raw="200 g courgettes", name="courgettes", qty_min=200.0, unit="g", position=1)], 1.0),
        ])
        assert len(needs) == 2

    def test_range_takes_the_upper_bound(self):
        """« 2–3 c.s. » : on achète pour 3, manquer coûte plus cher qu'avoir trop."""
        needs = build_needs([
            ("A", [Ingredient(raw="2–3 c.s. miel", name="miel",
                              qty_min=2.0, qty_max=3.0, unit="c.s.", position=1)], 1.0),
        ])
        assert needs[0].qty == 3.0


class TestFoundingBug:
    """Un condiment en stock ne doit jamais repartir sur la liste de courses."""

    @pytest.mark.parametrize("name,unit,qty", [
        ("miel", "c.s.", 2.0),
        ("sauce soja", "c.s.", 3.0),
    ])
    def test_stocked_condiments_never_reach_the_shopping_list(self, pantry, name, unit, qty):
        need = need_of(name, qty, unit)
        v = check_need(need, pantry, today=date(2026, 8, 4))
        assert v.outcome == ENOUGH, f"{name} repart en courses — le bug est revenu"
        assert v.pantry_item is not None

    def test_the_inventory_age_does_not_silently_flush_the_pantry(self, pantry):
        """La règle d'ancienneté ne doit pas devenir un moyen détourné de tout racheter."""
        old = parse_pantry(VAULT.replace("2026-07-11", "2025-01-01"))
        need = need_of("miel", 2.0, "c.s.")
        assert check_need(need, old, today=date(2026, 8, 4)).outcome == ENOUGH


class TestAliases:
    """Un alias déclaré réunit les graphies d'un même aliment, sans relâcher l'appariement."""

    @staticmethod
    def _item(name, status, rayon="Frais — Protéines"):
        return PantryItem(
            rayon=rayon, name=name, name_normalized=normalize_name(name), status=status
        )

    def test_declared_alias_lets_the_best_stocked_row_win(self):
        pantry = Pantry(
            items=[
                self._item("Œufs", STATUS_OUT),
                self._item("Œufs plein air", STATUS_OUT),
                self._item("Oeufs plein air x10", STATUS_OK),
            ],
            aliases={"oeufs plein air x10": "oeufs", "oeufs plein air": "oeufs"},
        )
        found = pantry.find(normalize_name("œufs"))
        assert found is not None
        assert found.name == "Oeufs plein air x10"
        assert found.status == STATUS_OK

    def test_without_a_declared_alias_the_matcher_is_not_loosened(self):
        """Sans alias, on ne devine pas : le comportement actuel est préservé."""
        pantry = Pantry(items=[
            self._item("Œufs", STATUS_OUT),
            self._item("Oeufs plein air x10", STATUS_OK),
        ])
        found = pantry.find(normalize_name("œufs"))
        assert found is not None
        assert found.status == STATUS_OUT

    def test_a_chain_of_aliases_still_forms_one_group(self):
        """Sans résolution transitive, le maillon du bout de chaîne sort du groupe."""
        pantry = Pantry(
            items=[
                self._item("Œufs", STATUS_OUT),
                self._item("Œufs plein air", STATUS_OUT),
                self._item("Oeufs plein air x10", STATUS_OK),
            ],
            aliases={"oeufs plein air": "oeufs",
                     "oeufs plein air x10": "oeufs plein air"},
        )
        found = pantry.find(normalize_name("œufs"))
        assert found is not None
        assert found.name == "Oeufs plein air x10"

    def test_alias_resolves_from_either_spelling(self):
        pantry = Pantry(
            items=[
                self._item("Poivrons rouges", STATUS_OUT, "Frais — Légumes & Fruits"),
                self._item("Poivron rouge", STATUS_OK, "Frais — Légumes & Fruits"),
            ],
            aliases={"poivron rouge": "poivrons rouges"},
        )
        for spelling in ("poivron rouge", "poivrons rouges"):
            found = pantry.find(spelling)
            assert found is not None, spelling
            assert found.status == STATUS_OK, spelling


class TestRealVault:
    """Contrôle de volume contre le vrai fichier du vault."""

    def test_real_file_parses_completely(self):
        from pathlib import Path
        path = Path(r"E:\Dr2\Dropbox\JULIEN\Obsidian\vault\Noyau\Cuisine\Garde-manger.md")
        if not path.exists():
            pytest.skip("vault local indisponible")
        p = parse_pantry(path.read_text(encoding="utf-8"))
        assert len(p.items) > 200
        assert p.updated is not None
        age = p.age_days()
        assert age is not None and age >= 0
        assert p.is_stale(today=p.updated + timedelta(days=15)) is True
