"""Import d'une page de livre — aucun réseau : on part de la sortie du modèle."""

from backend.book_import import (
    normalize_category,
    parse_yield,
    to_draft,
    to_markdown,
)


class TestParseYield:
    def test_persons(self):
        assert parse_yield("POUR 4 PERSONNES") == (4, "personne")

    def test_range_keeps_the_lower_bound(self):
        assert parse_yield("POUR 6-8 PERSONNES") == (6, "personne")

    def test_approximate_word(self):
        assert parse_yield("POUR UNE TRENTAINE DE BISCUITS") == (30, "biscuit")

    def test_unit_is_not_always_a_person(self):
        assert parse_yield("POUR 4 FOCCACINE") == (4, "foccacine")

    def test_unknown_yield_is_none_not_a_guess(self):
        assert parse_yield(None) == (None, None)
        assert parse_yield("Sans indication") == (None, None)


class TestCategory:
    def test_footer_category_is_normalized(self):
        assert normalize_category("Entrée") == "entrée"
        assert normalize_category("ENTREE") == "entrée"
        assert normalize_category("Plat") == "plat"

    def test_unknown_category_is_dropped(self):
        assert normalize_category("Chapitre 3") is None
        assert normalize_category(None) is None


PAGE = {
    "title": "Mafé au poisson et légumes",
    "subtitle": "type sénégalais",
    "category": "Plat",
    "prep_time_min": 50,
    "cook_time_min": None,
    "yield_raw": "POUR 4 PERSONNES",
    "ingredient_groups": [
        {"section": "Poisson et légumes",
         "lines": ["1,2 kg filets de merlu", "4 carottes"]},
        {"section": "Sauce mafé",
         "lines": ["200 g de pâte d'arachide", "Sel, poivre"]},
    ],
    "steps": ["Délayer la pâte d'arachide.", "Pocher le poisson 10 min."],
}


class TestToDraft:
    def test_lines_go_through_the_house_parser(self):
        d = to_draft(PAGE)
        first = d["ingredients"][0]
        assert first["qty_min"] == 1.2
        assert first["unit"] == "kg"
        assert "merlu" in first["name"]

    def test_sections_are_carried(self):
        d = to_draft(PAGE)
        assert d["ingredients"][0]["section"] == "Poisson et légumes"
        assert d["ingredients"][2]["section"] == "Sauce mafé"

    def test_positions_are_sequential_across_sections(self):
        assert [i["position"] for i in to_draft(PAGE)["ingredients"]] == [1, 2, 3, 4]

    def test_unquantified_line_is_kept_and_counted(self):
        """« Sel, poivre » reste, marquée `parsed=False`, et alimente le compteur."""
        d = to_draft(PAGE)
        assert d["ingredients"][3]["parsed"] is False
        assert d["ingredients"][3]["raw"] == "Sel, poivre"
        assert d["unparsed_count"] == 1

    def test_servings_only_when_the_unit_is_a_person(self):
        assert to_draft(PAGE)["servings"] == 4
        biscuits = dict(PAGE, yield_raw="POUR UNE TRENTAINE DE BISCUITS")
        d = to_draft(biscuits)
        assert d["yield_qty"] == 30 and d["yield_unit"] == "biscuit"
        assert d["servings"] is None, "une macro « par personne » sur des biscuits"

    def test_slug_is_derived_from_the_title(self):
        assert to_draft(PAGE)["slug"] == "mafe-au-poisson-et-legumes"

    def test_title_gets_an_initial_capital_without_lowering_the_rest(self):
        page = dict(PAGE, title="salade de poires au Pouligny-Saint-Pierre")
        assert to_draft(page)["title"] == "Salade de poires au Pouligny-Saint-Pierre"


class TestToMarkdown:
    def test_sections_become_subheadings(self):
        md = to_markdown(to_draft(PAGE))
        assert "## Ingrédients" in md
        assert "### Poisson et légumes" in md
        assert "### Sauce mafé" in md

    def test_raw_lines_are_written_verbatim(self):
        md = to_markdown(to_draft(PAGE))
        assert "- 1,2 kg filets de merlu" in md
        assert "- Sel, poivre" in md

    def test_a_blank_line_separates_a_list_from_the_next_subsection(self):
        md = to_markdown(to_draft(PAGE))
        lines = md.splitlines()
        idx = lines.index("### Sauce mafé")
        assert lines[idx - 1] == "", "sous-section collee a la liste precedente"

    def test_steps_are_numbered(self):
        md = to_markdown(to_draft(PAGE))
        assert "1. Délayer la pâte d'arachide." in md
        assert "2. Pocher le poisson 10 min." in md

    def test_frontmatter_carries_slug_and_source(self):
        md = to_markdown(to_draft(PAGE), source="Livre de fromages, p. 130")
        assert "slug: mafe-au-poisson-et-legumes" in md
        assert "Livre de fromages, p. 130" in md
        assert md.startswith("---\n")

    def test_imported_recipe_lands_as_to_test_not_active(self):
        assert "statut: a-tester" in to_markdown(to_draft(PAGE))

    def test_roundtrip_through_the_recipe_parser(self):
        """Le corps produit doit être relu par `parse_recipe_body` (cooking-manager-2#58)."""
        from cooking_manager.ingredients import parse_recipe_body

        md = to_markdown(to_draft(PAGE))
        body = md.split("---", 2)[2]
        content = parse_recipe_body(body)
        assert len(content.ingredients) == 4
        assert len(content.steps) == 2
