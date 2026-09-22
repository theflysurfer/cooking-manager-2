"""Parseur d'URL — extraction JSON-LD et forme du brouillon, sans réseau."""

import json

from backend.url_parser.draft import duration_minutes, is_usable, to_draft
from backend.url_parser.jsonld import _first_text, extract_from_jsonld
from backend.url_parser.models import Ingredient, Recipe, Step


def _page(payload: dict) -> str:
    return (
        '<html><head><script type="application/ld+json">'
        + json.dumps(payload)
        + "</script></head><body></body></html>"
    )


BASE = {
    "@type": "Recipe",
    "name": "Tarte aux pommes",
    "recipeIngredient": ["200 g de farine", "3 pommes"],
    "recipeInstructions": ["Étaler la pâte.", "Enfourner 30 min."],
}


class TestScalarCoercion:
    def test_a_category_given_as_a_list_is_read_not_crashed(self):
        recipe = extract_from_jsonld(_page(dict(BASE, recipeCategory=["Dessert"])))
        assert recipe is not None
        assert recipe.category == "Dessert"

    def test_a_name_given_as_an_object_is_read(self):
        recipe = extract_from_jsonld(_page(dict(BASE, name={"@value": "Tarte"})))
        assert recipe is not None
        assert recipe.title == "Tarte"

    def test_an_unreadable_shape_is_dropped_not_stringified(self):
        assert _first_text({"unknown": 1}) is None
        assert _first_text([]) is None
        assert _first_text(42) is None

    def test_a_list_category_survives_the_whole_draft_path(self):
        recipe = extract_from_jsonld(_page(dict(BASE, recipeCategory=["Dessert"])))
        assert recipe is not None
        assert to_draft(recipe)["recipe_type"] == "dessert"


class TestDraftShape:
    def _recipe(self) -> Recipe:
        return Recipe(
            title="Tarte aux pommes",
            ingredients=[
                Ingredient(position=1, raw="200 g de farine", name="farine",
                           quantity=200.0, quantity_max=200.0, unit="g", parsed=True)
            ],
            steps=[Step(position=1, text="Étaler la pâte.")],
        )

    def test_quantities_use_the_keys_the_reviewer_screen_reads(self):
        """Le brouillon de livre porte `qty_min` : celui d'URL doit parler la même langue."""
        ingredient = to_draft(self._recipe())["ingredients"][0]
        assert ingredient["qty_min"] == 200.0
        assert ingredient["qty_max"] == 200.0
        assert "quantity" not in ingredient

    def test_the_normalized_name_is_carried(self):
        assert to_draft(self._recipe())["ingredients"][0]["name_normalized"] == "farine"

    def test_usable_is_false_without_a_quantity(self):
        recipe = self._recipe()
        recipe.ingredients[0].quantity = None
        assert is_usable(recipe) is False
        assert to_draft(recipe)["usable"] is False

    def test_usable_is_false_without_a_step(self):
        recipe = self._recipe()
        recipe.steps = []
        assert is_usable(recipe) is False


class TestDuration:
    def test_hours_and_minutes(self):
        assert duration_minutes("2h 30min") == 150

    def test_nothing_readable_is_none_not_zero(self):
        assert duration_minutes("") is None
        assert duration_minutes("un moment") is None
