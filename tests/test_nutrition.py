"""Macros calculées depuis les ingrédients. Aucun réseau, aucune DB.

Les règles testées ici ne sont pas inventées : elles viennent du Coach Nutrition
du vault (`Coaches/Coach Nutrition/_coach.md`), Règle 1 et Règle 2bis.
"""

from cooking_manager.nutrition import (
    FoodEntry,
    Macros,
    load_food_base,
    match_entry,
    parse_food_sheet,
    recipe_macros,
    reconcile,
    to_grams,
)

COURGETTE = """---
type: generique
categorie: legumes
statut: partiel
source: ANSES-Ciqual
---

# 🥒 Courgette

## 1️⃣ Macros

| Métrique | /100g | Portion 150g |
|---|---|---|
| **Énergie** | 17 kcal | 25 kcal |
| **Protéines** | 2g | 3g |
| **Glucides** | 2g | 3g |
| **Fibres** | 1.1g | 1.6g |
| **Lipides** | 0.4g | 0.6g |
"""


LENTILLES = """---
type: generique
statut: partiel
source: ANSES-Ciqual
---

| Métrique | Crues /100g | Cuites /100g | Portion 80g cuits |
|---|---|---|---|
| **Énergie** | 339 kcal | 116 kcal | 93 kcal |
| **Protéines** | 25g | 9g | 7.2g |
| **Glucides** | 56g | 18g | 14.4g |
| **Fibres** | 11g | 4g | 3.2g |
| **Lipides** | 1.4g | 0.5g | 0.4g |
"""


class TestParseFoodSheet:
    def test_reads_frontmatter_and_the_per_100g_column(self):
        fm, forms = parse_food_sheet(COURGETTE)
        assert fm["source"] == "ANSES-Ciqual"
        assert fm["statut"] == "partiel"
        m = forms["100g"]
        assert (m.kcal, m.protein, m.carbs, m.fat) == (17, 2, 2, 0.4)

    def test_portion_columns_are_ignored(self):
        """« Portion 150g » n'est pas exprimée pour 100 g : la lire donnerait
        des macros rapportées à une base inconnue."""
        assert list(parse_food_sheet(COURGETTE)[1]) == ["100g"]

    def test_fibres_are_not_mistaken_for_a_macro(self):
        assert parse_food_sheet(COURGETTE)[1]["100g"].fat == 0.4

    def test_every_per_100g_column_is_kept_not_just_the_first(self):
        """⚠️ La 1re colonne n'est pas toujours « /100g » : `lentilles.md`
        porte « Crues » PUIS « Cuites ». Prendre la première donnait 339 kcal
        là où la recette veut 116 — facteur 3, en silence."""
        forms = parse_food_sheet(LENTILLES)[1]
        assert forms["crues"].kcal == 339
        assert forms["cuites"].kcal == 116


class TestReconcile:
    """Règle 2bis (erreur #25) : kcal annoncées vs P×4 + G×4 + L×9."""

    def test_coherent_values_reconcile(self):
        # 20×4 + 0×4 + 13×9 = 197 ≈ 208 → 5,3 %… donc NON réconcilié.
        r = reconcile(100.0, 10.0, 10.0, 2.0)  # 40+40+18 = 98, écart 2 %
        assert r["reconciled"] is True
        assert r["gap_pct"] == 2.0

    def test_structural_gap_is_reported_not_hidden(self):
        """Un écart n'est pas un bug (eau, cendres, fibres hors somme) — mais
        au-delà de 5 % il doit être MONTRÉ, jamais lissé."""
        r = reconcile(200.0, 10.0, 10.0, 2.0)  # 98 vs 200 → 51 %
        assert r["reconciled"] is False
        assert r["kcal_declared"] == 200.0 and r["kcal_rebuilt"] == 98.0
        assert r["gap_pct"] == 51.0

    def test_incomplete_data_never_pretends_to_reconcile(self):
        assert reconcile(100.0, None, 10.0, 2.0)["reconciled"] is None


class TestToGrams:
    def test_mass_units(self):
        assert to_grams(1.2, "kg") == 1200.0
        assert to_grams(200, "g") == 200.0

    def test_spoons_use_standard_volumes(self):
        assert to_grams(2, "c.s.") == 30.0
        assert to_grams(1, "c.c.") == 5.0

    def test_decimal_quantities_from_the_database(self):
        """asyncpg rend les colonnes NUMERIC en `Decimal`, qui ne se multiplie
        pas par un flottant. Les tests a base de float ne pouvaient pas le voir :
        le defaut n'est apparu qu'a l'appel reel (500 en production)."""
        from decimal import Decimal
        assert to_grams(Decimal("1.2"), "kg") == 1200.0

    def test_piece_units_are_NOT_converted(self):
        """« 4 carottes » n'a pas de poids sans un poids unitaire. Convertir
        « à peu près » fabriquerait des macros fausses."""
        assert to_grams(4, "pièce") is None
        assert to_grams(1, "gousse") is None
        assert to_grams(1, "botte") is None


def _entry(key, kcal, protein, kind="generique"):
    return FoodEntry(key=key, title=key, kind=kind, source="test",
                     forms={"100g": Macros(kcal=kcal, protein=protein,
                                           carbs=0.0, fat=0.0)})


def _multiform(key, **forms):
    return FoodEntry(
        key=key, title=key, kind="generique", source="test",
        forms={k: Macros(kcal=v, protein=0.0, carbs=0.0, fat=0.0)
               for k, v in forms.items()},
    )


class TestAmbiguousForms:
    """Règle 1 — pas d'hypothèse : entre lentilles crues et cuites, deviner
    c'est se tromper d'un facteur 3 sans que rien ne le signale."""

    LENTILLES = _multiform("lentilles", crues=339.0, cuites=116.0)

    def test_the_recipe_naming_the_form_resolves_it(self):
        macros, why = self.LENTILLES.macros_for("200 g de lentilles cuites")
        assert macros is not None
        assert macros.kcal == 116.0 and why == ""

    def test_an_unnamed_form_is_refused_not_guessed(self):
        macros, why = self.LENTILLES.macros_for("200 g de lentilles")
        assert macros is None
        assert "ambigu" in why

    def test_a_single_form_needs_no_disambiguation(self):
        macros, why = _entry("courgette", 17, 2).macros_for("300 g de courgette")
        assert macros is not None
        assert macros.kcal == 17 and why == ""


class TestMatchEntry:
    BASE = {"courgette": _entry("courgette", 17, 2),
            "chevre": _entry("chevre", 300, 20),
            "creme fraiche": _entry("creme fraiche", 300, 2)}

    def test_exact_match(self):
        found = match_entry("courgette", self.BASE)
        assert found is not None and found.key == "courgette"

    def test_longest_prefix_wins(self):
        found = match_entry("chevre tres sec", self.BASE)
        assert found is not None and found.key == "chevre"

    def test_no_fuzzy_match(self):
        """« crème de coco » ne doit PAS rencontrer « crème fraîche » : un faux
        appariement produit un nombre faux et invisible."""
        assert match_entry("creme de coco", self.BASE) is None

    def test_unknown_is_none_not_a_guess(self):
        assert match_entry("brocciu", self.BASE) is None


def _ing(raw, name_normalized, qty, unit, optional=False):
    return {"raw": raw, "name": raw, "name_normalized": name_normalized,
            "qty_min": qty, "unit": unit, "is_optional": optional}


class TestRecipeMacros:
    BASE = {"courgette": _entry("courgette", 17, 2),
            "chevre": _entry("chevre", 300, 20)}

    def test_sums_over_resolved_ingredients(self):
        ings = [_ing("300 g de courgette", "courgette", 300, "g")]
        m = recipe_macros(ings, self.BASE)
        assert m.kcal == 51.0        # 17 × 3
        assert m.protein == 6.0

    def test_unconvertible_unit_lands_in_unresolved_with_a_reason(self):
        ings = [_ing("4 carottes", "carottes", 4, "pièce")]
        m = recipe_macros(ings, self.BASE)
        assert m.kcal == 0.0
        assert len(m.unresolved) == 1
        assert "convertible" in m.unresolved[0].reason

    def test_missing_food_sheet_lands_in_unresolved(self):
        ings = [_ing("200 g de brocciu", "brocciu", 200, "g")]
        m = recipe_macros(ings, self.BASE)
        assert m.unresolved[0].reason == "aucune fiche aliment"

    def test_coverage_reports_what_was_actually_counted(self):
        """Une somme partielle présentée comme un total est le « nombre faux
        avec l'aplomb d'un nombre juste » que la Règle 1 interdit."""
        ings = [_ing("300 g de courgette", "courgette", 300, "g"),
                _ing("4 carottes", "carottes", 4, "pièce"),
                _ing("1 oignon", "oignon", 1, "pièce")]
        m = recipe_macros(ings, self.BASE)
        assert m.coverage < 0.4
        assert len(m.unresolved) == 2

    def test_optional_ingredients_do_not_penalise_coverage(self):
        ings = [_ing("300 g de courgette", "courgette", 300, "g"),
                _ing("1 pincée de sel (optionnel)", "sel", 1, "pincée", optional=True)]
        m = recipe_macros(ings, self.BASE)
        assert m.coverage == 1.0

    def test_empty_recipe_is_safe(self):
        m = recipe_macros([], self.BASE)
        assert m.coverage == 0.0 and m.kcal == 0.0


class TestLoadFoodBase:
    def test_brand_sheet_wins_over_generic_on_the_same_key(self, tmp_path):
        """Hiérarchie du coach : l'étiquette prime sur le générique CIQUAL."""
        (tmp_path / "generiques").mkdir()
        (tmp_path / "marques").mkdir()
        sheet = "---\ntype: {t}\nsource: {s}\n---\n\n| M | /100g |\n|---|---|\n| **Énergie** | {k} kcal |\n"
        (tmp_path / "generiques" / "feta.md").write_text(
            sheet.format(t="generique", s="ANSES-Ciqual", k=264), encoding="utf-8")
        (tmp_path / "marques" / "feta.md").write_text(
            sheet.format(t="marque", s="Étiquette", k=250), encoding="utf-8")
        base = load_food_base(tmp_path)
        assert base["feta"].kind == "marque"
        assert base["feta"].forms["100g"].kcal == 250

    def test_missing_root_is_safe(self, tmp_path):
        assert load_food_base(tmp_path / "absent") == {}
