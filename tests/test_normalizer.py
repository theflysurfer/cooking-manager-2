"""Unitaires — normalisation du frontmatter. Aucun réseau, aucune DB.

Le slug de menu est la clé naturelle qui a remplacé le `DELETE FROM menu` :
s'il est instable ou vide, l'upsert se remet à dupliquer ou à écraser.
"""

from cooking_manager.normalizer import normalize_menu, normalize_recipe, slugify


class TestSlugify:
    def test_strips_accents_and_punctuation(self):
        assert slugify("Semaine du 3 au 7 août") == "semaine-du-3-au-7-aout"

    def test_collapses_separators(self):
        assert slugify("Menu  —  semaine   #32") == "menu-semaine-32"

    def test_is_stable(self):
        title = "Gratin courgettes-ricotta & feta"
        assert slugify(title) == slugify(title)

    def test_never_returns_empty(self):
        assert slugify("") == "sans-titre"
        assert slugify("—  ///  —") == "sans-titre"

    def test_ascii_only(self):
        assert slugify("Crème brûlée à l'ancienne").isascii()


class TestMenuSlug:
    def test_derived_from_filename_when_absent(self):
        data, warnings = normalize_menu({
            "title": "Menu semaine du 2026-05-25",
            "_source_path": "/vault/Noyau/Cuisine/Menus/2026-05-25_menu.md",
        })
        assert data["slug"] == "2026-05-25_menu"
        assert not warnings

    def test_explicit_slug_wins_over_filename(self):
        data, _ = normalize_menu({
            "title": "Peu importe",
            "slug": "slug-explicite",
            "_source_path": "/vault/Menus/autre-nom.md",
        })
        assert data["slug"] == "slug-explicite"

    def test_warns_when_no_slug_can_be_derived(self):
        """Un menu sans slug ni fichier source violerait le NOT NULL en base :
        il doit être signalé, pas ingéré en silence."""
        data, warnings = normalize_menu({"title": "Menu orphelin"})
        assert not data.get("slug")
        assert any("slug" in w for w in warnings)

    def test_french_keys_are_aliased(self):
        data, _ = normalize_menu({
            "title": "T", "statut": "propose",
            "semaine_debut": "2026-08-03",
            "_source_path": "/x/m.md",
        })
        assert data["status"] == "proposed"
        assert data["week_start"] == "2026-08-03"

    def test_meals_are_preserved_untouched(self):
        """`meals` porte la structure jour — le normalizer ne doit pas y toucher."""
        meals = [{"day": "lundi", "lunch": "Salade", "dinner": "Curry"}]
        data, _ = normalize_menu({"title": "T", "meals": meals, "_source_path": "/x/m.md"})
        assert data["meals"] == meals


class TestRecipeNormalization:
    def test_macros_french_keys_are_aliased(self):
        data, _ = normalize_recipe({
            "title": "R", "slug": "r",
            "macros_per_portion_julien": {"kcal": 347, "prot": 65.5, "gluc": 14.6, "lip": 1},
        })
        assert data["macros"] == {"kcal": 347, "protein": 65.5, "carbs": 14.6, "fat": 1}

    def test_protein_density_is_computed(self):
        data, _ = normalize_recipe({
            "title": "R", "slug": "r",
            "macros_per_portion_julien": {"kcal": 347, "prot": 65.5},
        })
        assert data["protein_density"] == round(65.5 / 347, 3)

    def test_portions_base_maps_to_servings(self):
        data, _ = normalize_recipe({"title": "R", "slug": "r", "portions_base": 4})
        assert data["servings"] == 4
