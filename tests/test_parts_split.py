from cooking_manager.convives import Convive
from cooking_manager.parts import Share, apply_repairs, shares_for
from cooking_manager.substitutions import (
    IngredientRepair,
    Substitution,
    SubstitutionRule,
)

RULE = SubstitutionRule(source="poulet", target="dorade", reason="four méditerranéen",
                        priority=10)
SUB = Substitution(source="poulet", target="dorade", reason="four méditerranéen",
                   confidence=1.0, rule=RULE)
REPAIR = IngredientRepair(ingredient="8 pilons de poulet", diet="pescetarian",
                          substitution=SUB)

INGREDIENTS = [
    {"name": "pilons de poulet", "name_normalized": "pilon de poulet",
     "qty_min": 8, "qty_max": None, "unit": "pièce", "raw": "8 pilons de poulet"},
    {"name": "patates douces", "name_normalized": "patate douce",
     "qty_min": 1, "qty_max": None, "unit": "kg", "raw": "1 kg patates douces"},
]

class TestSharesFor:
    def test_only_restrictive_diets_carry_a_share(self):
        table = [Convive(name="Julien", diet="standard"),
                 Convive(name="Clémence", diet="pescetarian")]
        shares = shares_for(table, covers=4)
        assert list(shares) == ["pescetarian"]
        assert shares["pescetarian"].fraction == 0.25

    def test_a_whole_pescetarian_table_takes_everything(self):
        table = [Convive(name="Clémence", diet="pescetarian")]
        assert shares_for(table, covers=1)["pescetarian"].fraction == 1.0

class TestApplyRepairs:
    SHARES = {"pescetarian": Share("pescetarian", ("Clémence",), 4)}

    def test_the_line_is_split_in_two(self):
        out = apply_repairs(INGREDIENTS, [REPAIR], self.SHARES)
        names = [o["name"] for o in out]
        assert names == ["dorade", "pilons de poulet", "patates douces"]

    def test_quantities_follow_the_share(self):
        out = apply_repairs(INGREDIENTS, [REPAIR], self.SHARES)
        assert out[0]["qty_min"] == 2.0
        assert out[1]["qty_min"] == 6.0

    def test_the_substitute_says_who_it_is_for(self):
        out = apply_repairs(INGREDIENTS, [REPAIR], self.SHARES)
        assert out[0]["raw"] == "dorade (part de Clémence)"
        assert out[0]["substituted_for"] == "8 pilons de poulet"

    def test_untouched_lines_are_left_alone(self):
        out = apply_repairs(INGREDIENTS, [REPAIR], self.SHARES)
        assert out[2] == dict(INGREDIENTS[1])

    def test_a_repair_without_a_known_share_is_ignored(self):
        out = apply_repairs(INGREDIENTS, [REPAIR], {})
        assert [o["name"] for o in out] == ["pilons de poulet", "patates douces"]
        assert out[0]["qty_min"] == 8

    def test_a_full_share_removes_the_original(self):
        shares = {"pescetarian": Share("pescetarian", ("Clémence",), 1)}
        out = apply_repairs(INGREDIENTS, [REPAIR], shares)
        assert [o["name"] for o in out] == ["dorade", "patates douces"]

    def test_no_repair_changes_nothing(self):
        assert apply_repairs(INGREDIENTS, [], self.SHARES) == [dict(i) for i in INGREDIENTS]

class TestDeclaredDiets:
    TABLE = [Convive(name="Julien", diet="standard"),
             Convive(name="Clémence", diet="pescetarian")]

    def test_a_declared_part_covers_its_diet(self):
        from cooking_manager.parts import declared_diets
        lines = [{"raw": "240 g pois chiches cuits (part de Clémence)"},
                 {"raw": "8 pilons de poulet"}]
        assert declared_diets(lines, self.TABLE) == {"pescetarian"}

    def test_no_declared_part_leaves_the_engine_its_job(self):
        from cooking_manager.parts import declared_diets
        assert declared_diets([{"raw": "8 pilons de poulet"}], self.TABLE) == set()

    def test_a_part_for_someone_else_does_not_cover_a_diet(self):
        from cooking_manager.parts import declared_diets
        lines = [{"raw": "concombre (servi à part pour Léa)"}]
        assert declared_diets(lines, self.TABLE) == set()
