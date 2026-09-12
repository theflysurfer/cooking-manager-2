SHEET_KJ = """---
title: Pignons de pin
---

## Macros pour 100 g

| Nutriment | Valeur |
|---|---|
| Energie | 2820 kJ (673 kcal) |
| Proteines | 13,7 g |
| Glucides | 4,0 g |
| Lipides | 68,4 g |
"""

"""Macros calculées depuis les ingrédients. Aucun réseau, aucune DB."""

from cooking_manager.nutrition import (
    FoodEntry,
    Macros,
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
        """« Portion 150g » n'est pas exprimée pour 100 g : la lire donnerait"""
        assert list(parse_food_sheet(COURGETTE)[1]) == ["100g"]

    def test_fibres_are_not_mistaken_for_a_macro(self):
        assert parse_food_sheet(COURGETTE)[1]["100g"].fat == 0.4

    def test_every_per_100g_column_is_kept_not_just_the_first(self):
        """⚠️ La 1re colonne n'est pas toujours « /100g » : `lentilles.md`"""
        forms = parse_food_sheet(LENTILLES)[1]
        assert forms["crues"].kcal == 339
        assert forms["cuites"].kcal == 116

MOZZARELLA = """---
type: generique
source: ANSES-Ciqual
---

# Mozzarella

## Macros pour 100g

| Nutriment | Valeur |
|---|---|
| Énergie | 224 kcal |
| Protéines | 18g |
| Glucides | 1g |
| Lipides | 17g (dont AGS ~11g) |
"""

class TestThirdTableShape:
    """« | Nutriment | Valeur | », base annoncée par le TITRE DE SECTION."""

    def test_value_column_is_read_when_the_document_says_pour_100g(self):
        forms = parse_food_sheet(MOZZARELLA)[1]
        assert forms["100g"].kcal == 224
        assert forms["100g"].protein == 18
        assert forms["100g"].fat == 17

    def test_without_the_mention_the_table_is_ignored_not_assumed(self):
        """Sans « pour 100 g » explicite, rapporter les valeurs à une base"""
        text = MOZZARELLA.replace("## Macros pour 100g", "## Macros")
        assert parse_food_sheet(text)[1] == {}

class TestFrontmatterNullString:
    """#85 — `null` en YAML doit devenir None, pas la chaîne `"null"`."""

    def test_null_becomes_none(self):
        text = """---\ntitle: Pain complet\nciqual_code: null\nmarque: null\nnature: None\n---\n"""
        fm, _ = parse_food_sheet(text)
        assert fm["title"] == "Pain complet"
        assert fm["ciqual_code"] is None
        assert fm["marque"] is None
        assert fm["nature"] is None

    def test_empty_value_becomes_none(self):
        text = """---\ntitle: Test\nfoo:\n---\n"""
        fm, _ = parse_food_sheet(text)
        assert fm["foo"] is None


class TestReconcile:
    """Règle 2bis (erreur #25) : kcal annoncées vs P×4 + G×4 + L×9."""

    def test_coherent_values_reconcile(self):
        r = reconcile(100.0, 10.0, 10.0, 2.0)
        assert r["reconciled"] is True
        assert r["gap_pct"] == 2.0

    def test_structural_gap_is_reported_not_hidden(self):
        """Un écart n'est pas un bug (eau, cendres, fibres hors somme) — mais"""
        r = reconcile(200.0, 10.0, 10.0, 2.0)
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
        """asyncpg rend les colonnes NUMERIC en `Decimal`, qui ne se multiplie"""
        from decimal import Decimal
        assert to_grams(Decimal("1.2"), "kg") == 1200.0

    def test_piece_units_are_NOT_converted(self):
        """« 4 carottes » n'a pas de poids sans un poids unitaire. Convertir"""
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
    """Règle 1 — pas d'hypothèse : entre lentilles crues et cuites, deviner"""

    LENTILLES = _multiform("lentilles", crues=339.0, cuites=116.0)

    def test_the_recipe_naming_the_form_resolves_it(self):
        macros, why = self.LENTILLES.macros_for("200 g de lentilles cuites")
        assert macros is not None
        assert macros.kcal == 116.0 and why == ""

    def test_an_unnamed_form_defaults_to_raw(self):
        """ADR 0019 : forme non nommée → cru (une recette pèse l'ingrédient cru)."""
        macros, why = self.LENTILLES.macros_for("200 g de lentilles")
        assert macros is not None
        assert macros.kcal == 339.0 and why == ""

    def test_a_form_without_raw_stays_ambiguous(self):
        """Sans forme crue au tableau, on ne devine pas : deux cuissons, aucun défaut."""
        entry = _multiform("poulet", grille=200.0, roti=250.0)
        macros, why = entry.macros_for("200 g de poulet")
        assert macros is None and "ambigu" in why

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

    def test_variety_words_find_the_generic_by_token_subset(self):
        """« riz basmati complet » trouve « riz complet » (clé ⊆ ingrédient)."""
        base = {"riz complet": _entry("riz complet", 350, 8),
                "riz": _entry("riz", 130, 3)}
        found = match_entry("riz basmati complet", base)
        assert found is not None and found.key == "riz complet"

    def test_a_state_key_never_matches_a_bare_ingredient(self):
        """« patate douce cuite » (clé) ne s'applique pas à « patate douce » pesée crue."""
        base = {"patate douce cuite": _entry("patate douce cuite", 90, 2)}
        assert match_entry("patate douce", base) is None
        found = match_entry("patate douce cuite", base)
        assert found is not None and found.key == "patate douce cuite"

    def test_no_fuzzy_match(self):
        """« crème de coco » ne doit PAS rencontrer « crème fraîche » : un faux"""
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
        assert m.kcal == 51.0
        assert m.protein == 6.0

    def test_unconvertible_unit_lands_in_unresolved_with_a_reason(self):
        """Une pièce sans poids connu ni parenthèse reste non convertible."""
        ings = [_ing("2 machins", "machin", 2, "pièce")]
        m = recipe_macros(ings, self.BASE)
        assert m.kcal == 0.0
        assert len(m.unresolved) == 1
        assert "convertible" in m.unresolved[0].reason

    def test_parenthetical_grams_resolve_a_counted_unit(self):
        """« 2 courgettes (environ 300 g) » : le poids est écrit dans la ligne."""
        ings = [_ing("2 courgettes (environ 300 g)", "courgette", 2, "pièce")]
        m = recipe_macros(ings, self.BASE)
        assert m.kcal == 51.0 and len(m.resolved) == 1

    def test_piece_table_resolves_a_known_vegetable(self):
        """« 2 courgettes » sans poids : table poids/pièce (courgette ~150 g)."""
        ings = [_ing("2 courgettes", "courgette", 2, "pièce")]
        m = recipe_macros(ings, self.BASE)
        assert m.kcal == 51.0 and len(m.resolved) == 1

    def test_seasonings_do_not_penalise_coverage(self):
        """Sel et poivre non optionnels ne comptent pas comme non résolus."""
        ings = [_ing("300 g de courgette", "courgette", 300, "g"),
                _ing("sel", "sel", None, None),
                _ing("poivre du moulin", "poivre", None, None)]
        m = recipe_macros(ings, self.BASE)
        assert m.coverage == 1.0 and not m.unresolved

    def test_missing_food_sheet_lands_in_unresolved(self):
        ings = [_ing("200 g de brocciu", "brocciu", 200, "g")]
        m = recipe_macros(ings, self.BASE)
        assert m.unresolved[0].reason == "aucune fiche aliment"

    def test_coverage_reports_what_was_actually_counted(self):
        """Une somme partielle présentée comme un total est le « nombre faux"""
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

class TestEnergyUnit:
    """« 2820 kJ (673 kcal) » : la bonne valeur est dans la cellule, il suffit de la lire."""

    def test_kcal_wins_over_the_kilojoules_beside_it(self):
        from cooking_manager.nutrition import read_energy
        assert read_energy("2820 kJ (673 kcal)") == 673.0

    def test_kilojoules_alone_are_converted(self):
        from cooking_manager.nutrition import read_energy
        assert read_energy("2820 kJ") == 674.0

    def test_a_bare_number_stays_as_it_is(self):
        from cooking_manager.nutrition import read_energy
        assert read_energy("140") == 140.0

    def test_an_impossible_energy_is_refused_not_stored(self):
        """Aucun aliment ne depasse ~900 kcal/100 g : l'huile pure plafonne a 900."""
        from cooking_manager.nutrition import read_energy
        assert read_energy("2820") is None

    def test_a_sheet_in_kilojoules_yields_kcal(self):
        from cooking_manager.nutrition import parse_food_sheet
        sheet = SHEET_KJ
        _, forms = parse_food_sheet(sheet)
        assert forms["100g"].kcal == 673.0
