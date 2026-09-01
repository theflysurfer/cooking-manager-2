"""La passe de dédoublonnage propose, elle ne tranche pas (ADR 0002)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pantry_dedup_report import Row, find_candidates, _significant_words


def _row(id_, name, normalized, section="Frais — Protéines", status="ok", source="vault"):
    return Row(id_, name, normalized, section, "", status, source)


def _pairs(rows):
    return {
        tuple(sorted((c.canonical.id, c.other.id))) for c in find_candidates(rows)
    }


class TestSignificantWords:
    def test_strips_plural_and_packaging(self):
        assert _significant_words("oeufs plein air x10") == ["oeuf", "plein", "air"]

    def test_keeps_short_words_intact(self):
        """« riz » ne doit pas devenir « ri » : la coupe du pluriel exige deux lettres avant."""
        assert _significant_words("riz") == ["riz"]

    def test_drops_articles(self):
        assert _significant_words("gesiers de canard confits") == ["gesier", "canard", "confit"]


class TestCandidates:
    def test_singular_plural_pair_is_proposed(self):
        rows = [_row(1, "Poivrons rouges", "poivrons rouges"),
                _row(2, "Poivron rouge", "poivron rouge", source="receipt")]
        assert _pairs(rows) == {(1, 2)}

    def test_one_spelling_refining_another_is_proposed(self):
        rows = [_row(1, "Œufs", "oeufs"),
                _row(2, "Oeufs plein air x10", "oeufs plein air x10", source="receipt")]
        assert _pairs(rows) == {(1, 2)}

    def test_contradictory_status_is_flagged(self):
        rows = [_row(1, "Œufs", "oeufs", status="out"),
                _row(2, "Oeufs plein air x10", "oeufs plein air x10", status="ok")]
        assert find_candidates(rows)[0].conflicting is True

    def test_shared_head_without_coverage_is_not_proposed(self):
        """« sauce tomate basilic » et « sauce soja » partagent un mot, pas un aliment."""
        rows = [_row(1, "Sauce tomate basilic", "sauce tomate basilic"),
                _row(2, "Sauce soja salée", "sauce soja salee")]
        assert _pairs(rows) == set()

    def test_ingredient_buried_in_another_product_is_not_proposed(self):
        """« oeufs » est inclus dans « nouilles aux œufs » sans être le même article."""
        rows = [_row(1, "Œufs", "oeufs"),
                _row(2, "Suzi Wan Nouilles aux œufs", "suzi wan nouilles aux oeufs")]
        assert _pairs(rows) == set()

    def test_vault_row_is_kept_as_canonical(self):
        rows = [_row(1, "Poivron rouge", "poivron rouge", source="receipt"),
                _row(2, "Poivrons rouges", "poivrons rouges", source="vault")]
        assert find_candidates(rows)[0].canonical.id == 2
