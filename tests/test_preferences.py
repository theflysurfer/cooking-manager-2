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
