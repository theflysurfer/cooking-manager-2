"""Unitaires — parser d'ingrédients et d'étapes.

Le contrat central : **aucune ligne ne disparaît jamais**. Une quantité non
comprise doit rester visible à l'écran (`raw` conservé, `parsed=False`), parce
qu'un ingrédient avalé en silence, c'est un achat manqué qu'on découvre en
cuisine — trop tard.
"""

import pytest

from cooking_manager.ingredients import (
    normalize_name,
    parse_ingredient,
    parse_recipe_body,
)


class TestQuantities:
    def test_simple(self):
        ing = parse_ingredient("350 g skyr nature 0%", 1)
        assert (ing.qty_min, ing.unit, ing.parsed) == (350.0, "g", True)
        assert ing.name == "skyr nature 0%"

    def test_approximate_prefix(self):
        assert parse_ingredient("~300 g abricots congelés", 1).qty_min == 300.0

    def test_range_keeps_both_bounds(self):
        """« 2–3 c.s. » : on garde le min ET le max, la liste de courses
        prendra le max, la fiche affichera la fourchette."""
        ing = parse_ingredient("2–3 c.s. lait entier", 1)
        assert (ing.qty_min, ing.qty_max, ing.unit) == (2.0, 3.0, "c.s.")

    def test_decimal_comma(self):
        assert parse_ingredient("1,5 kg pommes de terre", 1).qty_min == 1.5

    def test_written_fraction(self):
        assert parse_ingredient("1/2 c. à café de levure chimique", 1).qty_min == 0.5

    @pytest.mark.parametrize("glyph,expected", [("½", 0.5), ("¼", 0.25), ("¾", 0.75)])
    def test_typographic_fractions(self, glyph, expected):
        """Le vault écrit « ½ oignon rouge » avec le vrai caractère — invisible
        d'une regex numérique."""
        assert parse_ingredient(f"{glyph} oignon rouge, émincé", 1).qty_min == expected

    def test_mixed_quantity(self):
        assert parse_ingredient("1 ½ c.s. miel", 1).qty_min == 1.5


class TestUnits:
    @pytest.mark.parametrize("text,unit", [
        ("100 g eau", "g"),
        ("20 cl crème", "cl"),
        ("2 c. à soupe de beurre de cacahuète", "c.s."),
        ("1 c.c. extrait de vanille", "c.c."),
        ("1 pincée de sel", "pincée"),
        ("1 boîte de pois chiches", "boîte"),
        ("1 scoop whey", "scoop"),
    ])
    def test_unit_variants(self, text, unit):
        assert parse_ingredient(text, 1).unit == unit

    def test_dotted_unit_is_recognized(self):
        """Régression : `\\b` après « c.c. » ne peut JAMAIS matcher — le point et
        l'espace qui suit sont tous deux non-alphanumériques, donc il n'y a pas
        de frontière de mot. 15 ingrédients ressortaient en unité « pièce »."""
        ing = parse_ingredient("1 c.c. extrait de vanille (5 ml)", 1)
        assert ing.unit == "c.c."
        assert ing.name.startswith("extrait de vanille")
        assert not ing.name.startswith("c.c.")

    def test_bare_count_defaults_to_piece(self):
        ing = parse_ingredient("2 bananes bien mûres écrasées", 1)
        assert (ing.qty_min, ing.unit) == (2.0, "pièce")


class TestTolerance:
    def test_quantityless_line_is_kept_raw(self):
        """« Édulcorant au choix — qs » n'a pas de quantité : elle doit rester
        affichable, pas disparaître."""
        ing = parse_ingredient("Édulcorant au choix (stévia, érythritol) — qs", 1)
        assert ing.parsed is False
        assert ing.raw.startswith("Édulcorant")
        assert ing.name  # jamais vide : il y a toujours quelque chose à afficher

    def test_raw_is_always_preserved(self):
        for text in ["350 g farine", "Sel, poivre", "Huile d'olive pour la poêle", "???"]:
            assert parse_ingredient(text, 1).raw

    def test_optional_is_detected(self):
        for text in ["1 g gomme xanthane (texture, optionnel)",
                     "Édulcorant au choix",
                     "50 g noix — facultatif"]:
            assert parse_ingredient(text, 1).is_optional

    def test_markdown_bold_is_stripped(self):
        ing = parse_ingredient("**150 g** de chocolat noir 70%+", 1)
        assert ing.qty_min == 150.0


class TestNormalizeName:
    def test_matches_pantry_variants(self):
        """La clé d'appariement doit faire se rencontrer « miel » et
        « Miel bio (liquide) » — c'est ce qui évite de racheter du miel
        qu'on a déjà (incident du 2026-08-04)."""
        assert normalize_name("Miel bio (liquide)") == normalize_name("miel")

    def test_strips_accents_and_parentheses(self):
        assert normalize_name("Crème fraîche (30% MG)") == "creme fraiche"

    def test_strips_trailing_note(self):
        assert normalize_name("whey isolate — optionnel") == "whey isolate"


class TestRecipeBody:
    BODY = """
# Titre

## Ingrédients (1 pot Creami)

- 350 g skyr nature 0%
- 30 g whey isolate vanille (1 scoop)
- 1 c.c. extrait de vanille
- Édulcorant au choix — qs

**Variantes testées** : remplacer le skyr par du fromage blanc.

## Préparation (10 min + 24h congélation)

1. Fouetter tous les ingrédients.
2. Congeler 24h à plat.
3. Cycle Lite Ice Cream.

## Notes techniques

- Le pudding mix améliore la texture.
"""

    def test_extracts_ingredients_and_steps(self):
        content = parse_recipe_body(self.BODY)
        assert len(content.ingredients) == 4
        assert len(content.steps) == 3
        assert content.steps[0].text.startswith("Fouetter")

    def test_bold_note_closes_the_ingredient_list(self):
        """« **Variantes testées** : … » est une note, pas un ingrédient —
        sinon elle atterrit dans la liste de courses."""
        names = [i.name for i in parse_recipe_body(self.BODY).ingredients]
        assert not any("Variantes" in n for n in names)

    def test_later_sections_are_not_swallowed(self):
        """La section « Notes techniques » ne doit pas polluer les étapes."""
        content = parse_recipe_body(self.BODY)
        assert not any("pudding" in s.text for s in content.steps)

    def test_parse_rate(self):
        content = parse_recipe_body(self.BODY)
        assert content.parse_rate == 0.75  # 3 sur 4 (l'édulcorant n'a pas de quantité)

    def test_empty_body_is_safe(self):
        content = parse_recipe_body("")
        assert content.ingredients == [] and content.steps == []
        assert content.parse_rate == 1.0

    def test_positions_are_sequential(self):
        content = parse_recipe_body(self.BODY)
        assert [i.position for i in content.ingredients] == [1, 2, 3, 4]
        assert [s.position for s in content.steps] == [1, 2, 3]

    def test_steps_are_stripped_of_markdown(self):
        """Le corps est du markdown, l'app rend du texte : les étapes
        sortaient avec leurs `**` visibles (« congeler **24h minimum** »)."""
        body = "## Préparation\n\n1. Congeler **24h minimum** à plat.\n2. Cycle *Lite Ice Cream*.\n"
        steps = parse_recipe_body(body).steps
        assert steps[0].text == "Congeler 24h minimum à plat."
        assert steps[1].text == "Cycle Lite Ice Cream."
