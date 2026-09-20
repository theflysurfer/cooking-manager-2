from cooking_manager.convives import part_for

INGREDIENTS = [
    "8 pilons de poulet",
    "240 g pois chiches cuits, égouttés (part de Clémence)",
    "1 kg patates douces, en gros cubes",
]

class TestPartFor:
    def test_finds_the_part_of_a_named_convive(self):
        part = part_for("Clémence", INGREDIENTS)
        assert part is not None and part.startswith("240 g pois chiches")

    def test_accent_and_case_do_not_matter(self):
        assert part_for("clemence", INGREDIENTS) is not None

    def test_another_convive_has_no_part_here(self):
        assert part_for("Léa", INGREDIENTS) is None

    def test_the_servi_a_part_form_counts_too(self):
        ings = ["concombre, en rondelles (servi à part pour Léa)"]
        assert part_for("Léa", ings) is not None

    def test_a_mention_outside_parentheses_is_not_a_part(self):
        assert part_for("Clémence", ["poulet pour Clémence et les enfants"]) is None

    def test_no_ingredients_means_no_part(self):
        assert part_for("Clémence", []) is None
