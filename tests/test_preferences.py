from cooking_manager.preferences import check_preferences, load_rules

ROWS = [
    {"kind": "cap", "target": "saumon", "value": 1, "unit": "repas",
     "scope": "week", "reason": "élevage : oméga-3 faibles", "person": ""},
    {"kind": "rotate", "target": "poulet", "value": 2, "unit": "repas",
     "scope": "week", "reason": "rotation des protéines", "person": "Julien"},
    {"kind": "no_restriction", "target": "gluten", "value": None, "unit": "",
     "scope": "week", "reason": "", "person": "Léa"},
]

MEALS = [
    {"day": "lundi", "slot": "dinner", "dish": "Mafé au poisson",
     "ingredients": ["filet de cabillaud", "aubergines"]},
    {"day": "mardi", "slot": "dinner", "dish": "Pilons de poulet paprika-citron",
     "ingredients": ["pilons de poulet", "patates douces"]},
    {"day": "mercredi", "slot": "dinner", "dish": "Saumon teriyaki-sésame",
     "ingredients": ["filet de saumon", "asperges vertes"]},
    {"day": "jeudi", "slot": "lunch", "dish": "Wraps froids",
     "ingredients": ["blanc de poulet", "tortillas"]},
]

class TestLoadRules:
    def test_no_restriction_is_not_counted(self):
        assert len(load_rules(ROWS)) == 2

    def test_value_becomes_a_float(self):
        assert load_rules(ROWS)[0].value == 1.0

class TestCheckPreferences:
    def setup_method(self):
        self.rules = load_rules(ROWS)

    def test_cap_respected_is_not_breached(self):
        salmon = check_preferences(MEALS, self.rules)[0]
        assert salmon.count == 1 and salmon.breached is False

    def test_cap_exceeded_is_breached(self):
        meals = MEALS + [{"day": "samedi", "slot": "dinner", "dish": "Tartare",
                          "ingredients": ["pavé de saumon"]}]
        salmon = check_preferences(meals, self.rules)[0]
        assert salmon.count == 2 and salmon.breached is True

    def test_ingredient_counts_even_when_the_dish_is_silent(self):
        chicken = check_preferences(MEALS, self.rules)[1]
        assert chicken.count == 2
        assert {h["day"] for h in chicken.hits} == {"mardi", "jeudi"}

    def test_rotate_breaches_on_the_third_meal(self):
        meals = MEALS + [{"day": "vendredi", "slot": "dinner", "dish": "Poulet rôti",
                          "ingredients": []}]
        chicken = check_preferences(meals, self.rules)[1]
        assert chicken.count == 3 and chicken.breached is True

    def test_count_is_always_rendered(self):
        checks = check_preferences([], self.rules)
        assert [c.count for c in checks] == [0, 0]
        assert all(c.breached is False for c in checks)

    def test_day_scope_takes_the_worst_day(self):
        rules = load_rules([{"kind": "cap", "target": "poulet", "value": 1,
                             "unit": "repas", "scope": "day", "reason": "",
                             "person": ""}])
        meals = [
            {"day": "mardi", "slot": "lunch", "dish": "Poulet curry", "ingredients": []},
            {"day": "mardi", "slot": "dinner", "dish": "Poulet rôti", "ingredients": []},
            {"day": "jeudi", "slot": "dinner", "dish": "Cabillaud", "ingredients": []},
        ]
        check = check_preferences(meals, rules)[0]
        assert check.count == 2 and check.breached is True

    def test_maximize_breaches_when_below_target(self):
        rules = load_rules([{"kind": "maximize", "target": "legume", "value": 5,
                             "unit": "repas", "scope": "week", "reason": "",
                             "person": ""}])
        check = check_preferences(MEALS, rules)[0]
        assert check.count == 0 and check.breached is True

class TestMeasurable:
    """Un zéro sur une cible qu'aucun ingrédient ne porte n'est pas un constat."""

    VOCAB = ["filet de saumon", "pilons de poulet", "cabillaud", "courgettes"]

    def test_category_target_without_a_class_is_flagged_unmeasurable(self):
        rules = load_rules([{"kind": "minimize",
                             "target": "feculent a index glycemique eleve",
                             "value": None, "unit": "", "scope": "week",
                             "reason": "", "person": ""}])
        check = check_preferences(MEALS, rules, self.VOCAB)[0]
        assert check.count == 0 and check.breached is False
        assert check.measurable is False

    def test_real_target_absent_from_the_menu_stays_measurable(self):
        rules = load_rules([{"kind": "cap", "target": "courgette", "value": 1,
                             "unit": "repas", "scope": "week", "reason": "",
                             "person": ""}])
        check = check_preferences(MEALS, rules, self.VOCAB)[0]
        assert check.count == 0 and check.measurable is True

    def test_a_hit_is_proof_enough_without_vocabulary(self):
        check = check_preferences(MEALS, load_rules(ROWS), self.VOCAB)[0]
        assert check.count == 1 and check.measurable is True

class TestWhatCannotBeCounted:
    def test_a_cap_in_grams_is_not_a_meal_count(self):
        rules = load_rules([{"kind": "cap", "target": "sucres ajoutes", "value": 25,
                             "unit": "g", "scope": "day", "reason": "", "person": ""}])
        check = check_preferences(MEALS, rules, ["sucre roux"])[0]
        assert check.measurable is False and check.breached is False

    def test_sans_x_is_not_a_mention_of_x(self):
        rules = load_rules([{"kind": "cap", "target": "sucres ajoutes", "value": 1,
                             "unit": "repas", "scope": "week", "reason": "",
                             "person": ""}])
        meals = [{"day": "lundi", "slot": "snack", "dish": "Compote",
                  "ingredients": ["compote sans sucres ajoutés (100 g)"]}]
        check = check_preferences(meals, rules, ["compote sans sucres ajoutés"])[0]
        assert check.count == 0

    def test_a_real_sugar_still_counts(self):
        rules = load_rules([{"kind": "cap", "target": "sucre", "value": 1,
                             "unit": "repas", "scope": "week", "reason": "",
                             "person": ""}])
        meals = [{"day": "lundi", "slot": "snack", "dish": "Gâteau",
                  "ingredients": ["sucre roux"]}]
        assert check_preferences(meals, rules, ["sucre roux"])[0].count == 1

class TestProteinFamilies:
    from cooking_manager.preferences import families_in, meals_without_protein

    def test_a_class_target_counts_every_family(self):
        rules = load_rules([{"kind": "maximize", "target": "proteine animale",
                             "value": 5, "unit": "repas", "scope": "week",
                             "reason": "", "person": ""}])
        check = check_preferences(MEALS, rules, ["filet de saumon"])[0]
        assert check.count == 4 and check.measurable is True
        assert check.breached is True

    def test_rotate_on_a_class_counts_per_family(self):
        rules = load_rules([{"kind": "rotate", "target": "famille de proteine",
                             "value": 2, "unit": "repas", "scope": "week",
                             "reason": "", "person": ""}])
        meals = MEALS + [{"day": "vendredi", "slot": "dinner",
                          "dish": "Poulet rôti", "ingredients": []}]
        check = check_preferences(meals, rules, ["blanc de poulet"])[0]
        assert check.by_family["volaille"] == 3
        assert check.breached is True and check.measurable is True

    def test_a_meal_without_protein_is_named(self):
        from cooking_manager.preferences import meals_without_protein
        meals = MEALS + [{"day": "dimanche", "slot": "dinner",
                          "dish": "Risotto aux champignons et poivrons",
                          "ingredients": ["riz à risotto", "champignons"]}]
        holes = meals_without_protein(meals)
        assert [h["day"] for h in holes] == ["dimanche"]

    def test_parmesan_alone_is_not_a_protein_family(self):
        from cooking_manager.preferences import families_in
        assert families_in({"dish": "Risotto", "ingredients": ["parmesan"]}) == []

class TestLeftoversAreNotAHole:
    def test_a_leftovers_meal_is_not_counted_as_protein_less(self):
        from cooking_manager.preferences import meals_without_protein
        meals = [{"day": "vendredi", "slot": "lunch", "dish": "Restes de la poêlée",
                  "match_kind": "leftovers", "ingredients": []}]
        assert meals_without_protein(meals) == []
