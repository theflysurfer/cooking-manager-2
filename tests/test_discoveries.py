from cooking_manager.substitutions import (
    Discovery,
    IngredientRepair,
    Substitution,
    SubstitutionRule,
    prefer_discovered,
)

RULE = SubstitutionRule(source="poulet", target="dorade", reason="four", priority=10)
REPAIR = IngredientRepair(
    ingredient="8 pilons de poulet", diet="pescetarian",
    substitution=Substitution(source="poulet", target="dorade", reason="four",
                              confidence=1.0, rule=RULE),
)

class TestPreferDiscovered:
    def test_no_discovery_changes_nothing(self):
        kept, dropped = prefer_discovered([REPAIR], [])
        assert kept == [REPAIR] and dropped == []

    def test_a_success_overrides_the_rule(self):
        found = Discovery(original="poulet", substitute="pois chiches",
                          outcome="success", who_preferred="Clémence")
        kept, dropped = prefer_discovered([REPAIR], [found])
        assert kept[0].substitution.target == "pois chiches"
        assert "préféré par Clémence" in kept[0].substitution.reason
        assert dropped == []

    def test_a_failure_on_the_proposed_target_drops_the_repair(self):
        found = Discovery(original="poulet", substitute="dorade", outcome="failure",
                          who_preferred="Clémence")
        kept, dropped = prefer_discovered([REPAIR], [found])
        assert kept == []
        assert dropped[0].diet == "pescetarian"
        assert "failure" in dropped[0].reason

    def test_a_failure_on_another_target_is_not_our_business(self):
        found = Discovery(original="poulet", substitute="tofu", outcome="failure")
        kept, _ = prefer_discovered([REPAIR], [found])
        assert kept[0].substitution.target == "dorade"

    def test_a_success_wins_over_a_failure_on_the_same_source(self):
        discoveries = [
            Discovery(original="poulet", substitute="dorade", outcome="failure"),
            Discovery(original="poulet", substitute="crevettes", outcome="success"),
        ]
        kept, dropped = prefer_discovered([REPAIR], discoveries)
        assert kept[0].substitution.target == "crevettes" and dropped == []

    def test_a_discovery_on_another_ingredient_is_ignored(self):
        found = Discovery(original="boeuf", substitute="lentilles", outcome="success")
        kept, _ = prefer_discovered([REPAIR], [found])
        assert kept[0].substitution.target == "dorade"

    def test_a_discovery_that_confirms_the_rule_keeps_the_rule_reason(self):
        found = Discovery(original="poulet", substitute="dorade", outcome="success")
        kept, _ = prefer_discovered([REPAIR], [found])
        assert kept[0] is REPAIR


class TestBouillonIsNotAFish:
    """« 30 cl de bouillon de bœuf » rendait « lotte, 75 ml » — mesuré le 2026-09-20
    sur le chili con carne moissonné : la règle volaille existait, pas la bœuf."""

    def test_a_beef_stock_becomes_a_vegetable_stock(self):
        from cooking_manager.substitutions import RecipeContext, find_substitution
        context = RecipeContext(cooking_methods=("stew",))
        found = find_substitution("30 cl de bouillon de boeuf", context, "pescetarian")
        assert found is not None and "bouillon" in found.target

    def test_real_beef_still_becomes_a_fish(self):
        from cooking_manager.substitutions import RecipeContext, find_substitution
        context = RecipeContext(cooking_methods=("stew",))
        found = find_substitution("500 g de boeuf haché", context, "pescetarian")
        assert found is not None and "bouillon" not in found.target
