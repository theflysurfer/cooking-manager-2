from cooking_manager.food_repository import base_from_form_rows, base_from_rows


def form_row(key, label, kcal, name="Lentille"):
    return {"key": key, "name": name, "source": "ciqual", "kind": "generique",
            "label": label, "kcal": kcal, "protein": 1.0, "carbs": 2.0, "fat": 3.0}


class TestFormRows:
    def test_one_food_keeps_all_its_forms(self):
        """Deux lignes food_form d'un meme aliment = une entree, deux formes."""
        base = base_from_form_rows([form_row("lentille", "crues", 330.0),
                                    form_row("lentille", "cuites", 116.0)])
        assert list(base) == ["lentille"]
        macros, _ = base["lentille"].macros_for("lentilles cuites")
        assert macros is not None and macros.kcal == 116.0

    def test_a_single_form_resolves_without_the_name(self):
        base = base_from_form_rows([form_row("comte", "100g", 417.0, "Comte")])
        macros, _ = base["comte"].macros_for("comte")
        assert macros is not None and macros.kcal == 417.0

    def test_a_missing_macro_stays_none(self):
        row = form_row("mystere", "100g", None)
        row["protein"] = None
        base = base_from_form_rows([row])
        assert base["mystere"].forms["100g"].kcal is None


def food(key, name, kcal: float | None = 100.0, kind="generique", **kw):
    row = {"key": key, "name": name, "kind": kind,
           "macros_per_100g": {"form": "100g", "kcal": kcal, "protein": 1.0,
                               "carbs": 2.0, "fat": 3.0},
           "source": "ciqual", "category": None}
    row.update(kw)
    return row


class TestIndexing:
    def test_the_index_key_drops_particles(self):
        """`food.key` vaut « lait de coco » ; l'appariement veut « lait coco »."""
        base = base_from_rows([food("lait de coco", "Lait de coco")], [])
        assert "lait coco" in base
        assert base["lait coco"].title == "Lait de coco"

    def test_the_entry_keeps_the_storage_key(self):
        base = base_from_rows([food("lait de coco", "Lait de coco")], [])
        assert base["lait coco"].key == "lait de coco"

    def test_macros_are_read_for_100g(self):
        base = base_from_rows([food("comte", "Comté", kcal=417.0)], [])
        macros, reason = base["comte"].macros_for("comté")
        assert macros is not None and macros.kcal == 417.0
        assert reason == ""


class TestPrecedence:
    def test_a_product_outranks_its_food(self):
        """Un produit précis prime sur le générique CIQUAL — hiérarchie du coach."""
        base = base_from_rows(
            [food("comte", "Comté", kcal=417.0)],
            [{"name": "Comté Juraflore AOP", "food_key": "comte", "brand": "Juraflore",
              "macros_per_100g": {"form": "100g", "kcal": 389.0}, "status": "linked"}])
        assert base["comte"].kind == "marque"
        macros, _ = base["comte"].macros_for("comté")
        assert macros is not None and macros.kcal == 389.0

    def test_an_unlinked_product_never_shadows_a_food(self):
        """`a_rapprocher` veut dire « on ne sait pas » : il ne remplace rien."""
        base = base_from_rows(
            [food("comte", "Comté", kcal=417.0)],
            [{"name": "Comté Juraflore AOP", "food_key": None, "brand": "Juraflore",
              "macros_per_100g": {"form": "100g", "kcal": 389.0},
              "status": "a_rapprocher"}])
        macros, _ = base["comte"].macros_for("comté")
        assert macros is not None and macros.kcal == 417.0


class TestRefusal:
    def test_a_row_without_macros_is_absent_not_zeroed(self):
        base = base_from_rows([food("mystere", "Mystère", kcal=None)
                               | {"macros_per_100g": None}], [])
        assert "mystere" not in base

    def test_an_empty_base_is_empty(self):
        assert base_from_rows([], []) == {}
