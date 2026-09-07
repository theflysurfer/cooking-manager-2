from cooking_manager.food_units import FoodUnit, read_food_units

SHEET = """---
title: Auchan Bio Plein Air Oeufs
---

## Macros pour 100 g

| Nutriment | Valeur |
|---|---|
| Energie | 140 kcal |

## Par oeuf (~60g)

| Nutriment | Valeur |
|---|---|
| Energie | 84 kcal |
"""


class TestRead:
    def test_reads_the_unit_and_its_weight(self):
        assert read_food_units(SHEET) == [FoodUnit("pièce", 60.0)]

    def test_named_unit_is_kept(self):
        sheet = SHEET.replace("Par oeuf (~60g)", "Par gousse (~5 g)")
        assert read_food_units(sheet) == [FoodUnit("gousse", 5.0)]

    def test_several_units(self):
        sheet = SHEET + "\n## Par tranche (~30 g)\n\n| x | y |\n"
        assert read_food_units(sheet) == [FoodUnit("pièce", 60.0), FoodUnit("tranche", 30.0)]

    def test_scoop(self):
        sheet = SHEET.replace("Par oeuf (~60g)", "Par scoop (30 g)")
        assert read_food_units(sheet) == [FoodUnit("scoop", 30.0)]


class TestRefuse:
    def test_no_section_yields_nothing(self):
        assert read_food_units("## Macros pour 100 g\n\n| a | b |\n") == []

    def test_a_section_without_weight_is_not_guessed(self):
        """« Par portion » sans grammage ne donne rien — pas d'hypothèse."""
        assert read_food_units("## Par portion\n\n| a | b |\n") == []

    def test_the_100g_section_is_not_a_unit(self):
        assert FoodUnit("pièce", 100.0) not in read_food_units("## Macros pour 100 g\n")
