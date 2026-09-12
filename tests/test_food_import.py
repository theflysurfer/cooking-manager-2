from pathlib import Path

from backend.food_import import build_records

GENERIC = """---
title: Pain complet
slug: pain-complet
categorie: feculent
type_produit: pain
source_macros: ciqual
date_maj: 2026-07-11
ciqual_code: "7010"
---

## Macros pour 100 g

| Nutriment | Valeur |
|---|---|
| Energie | 247 kcal |
| Proteines | 9,0 g |
| Glucides | 44,0 g |
| Lipides | 2,8 g |
"""

BRANDED = """---
title: Auchan Bio Plein Air Oeufs x12
slug: auchan-bio-plein-air-oeufs-x12
marque: Auchan
categorie: proteine
type_produit: oeufs
nutriscore: A
---

## Macros pour 100 g

| Nutriment | Valeur |
|---|---|
| Energie | 140 kcal |

## Par oeuf (~60g)

| Nutriment | Valeur |
|---|---|
| Energie | 84 kcal |
"""


def make_vault(tmp_path: Path) -> Path:
    (tmp_path / "generiques").mkdir()
    (tmp_path / "marques").mkdir()
    (tmp_path / "generiques" / "pain-complet.md").write_text(GENERIC, encoding="utf-8")
    (tmp_path / "marques" / "oeufs.md").write_text(BRANDED, encoding="utf-8")
    (tmp_path / "_index.md").write_text("# Index", encoding="utf-8")
    return tmp_path


class TestFoods:
    def test_generic_sheets_become_foods(self, tmp_path):
        plan = build_records(make_vault(tmp_path))
        keys = {f["key"] for f in plan.foods}
        assert "pain complet" in keys

    def test_index_files_are_skipped(self, tmp_path):
        plan = build_records(make_vault(tmp_path))
        assert all("index" not in f["key"] for f in plan.foods)

    def test_a_null_brand_does_not_make_a_product(self, tmp_path):
        """49 fiches de generiques/ portent « marque: null » — la CHAÎNE « null »."""
        root = make_vault(tmp_path)
        sheet = root / "generiques" / "pain-complet.md"
        sheet.write_text(sheet.read_text(encoding="utf-8")
                         .replace("slug: pain-complet", "slug: pain-complet\nmarque: null"),
                         encoding="utf-8")
        plan = build_records(root)
        assert "pain complet" in {f["key"] for f in plan.foods}
        assert all(p["brand"] != "null" for p in plan.products)


class TestProducts:
    def test_branded_sheets_become_products(self, tmp_path):
        plan = build_records(make_vault(tmp_path))
        assert len(plan.products) == 1
        assert plan.products[0]["brand"] == "Auchan"

    def test_the_packaging_leaves_the_name(self, tmp_path):
        plan = build_records(make_vault(tmp_path))
        product = plan.products[0]
        assert product["pack_count"] == 12
        assert "x12" not in product["name"]

    def test_a_product_without_a_matching_food_is_marked(self, tmp_path):
        """Aucun générique « oeufs » ici : le produit entre `a_rapprocher`."""
        plan = build_records(make_vault(tmp_path))
        assert plan.products[0]["status"] == "a_rapprocher"
        assert plan.products[0]["food_key"] is None


class TestCollisions:
    def test_two_sheets_on_one_key_are_held_not_arbitrated(self, tmp_path):
        """Deux fiches sur une clé : l'upsert gardait la dernière lue, en silence."""
        root = make_vault(tmp_path)
        twin = root / "generiques" / "pain-complet-bis.md"
        twin.write_text(GENERIC.replace("title: Pain complet", "title: pain-complet")
                        .replace("| Energie | 247 kcal |", "| Energie | 235 kcal |"),
                        encoding="utf-8")
        plan = build_records(root)
        assert "pain complet" not in {f["key"] for f in plan.foods}
        assert plan.collisions[0]["key"] == "pain complet"
        assert len(plan.collisions[0]["sheets"]) == 2

class TestUnits:
    def test_usage_units_are_collected(self, tmp_path):
        plan = build_records(make_vault(tmp_path))
        assert {"unit": "pièce", "grams": 60.0} in [
            {"unit": u["unit"], "grams": u["grams"]} for u in plan.units
        ]


def with_nature(tmp_path: Path, nature: str) -> Path:
    """Le même vault, dont la fiche de marque déclare une nature."""
    root = make_vault(tmp_path)
    sheet = root / "marques" / "oeufs.md"
    sheet.write_text(
        sheet.read_text(encoding="utf-8").replace(
            "nutriscore: A", "nutriscore: A" + chr(10) + f"nature: {nature}"
        ),
        encoding="utf-8",
    )
    return root


class TestProductNature:
    """La nature borne ce qu'un `food_key` vide veut dire — refs #90."""

    def test_a_declared_nature_is_read(self, tmp_path):
        plan = build_records(with_nature(tmp_path, "single"))
        assert plan.products[0]["nature"] == "single"

    def test_an_invented_nature_is_refused(self, tmp_path):
        import pytest
        with pytest.raises(ValueError, match="inconnue du vocabulaire"):
            build_records(with_nature(tmp_path, "plat"))

    def test_an_absent_nature_stays_absent(self, tmp_path):
        plan = build_records(make_vault(tmp_path))
        assert plan.products[0]["nature"] is None

    def test_the_vocabulary_carries_the_two_natures(self):
        from backend.food_import import product_natures
        assert product_natures() == ("single", "composite")



class TestBrandInTheName:
    """« Auchan Pignons de Pin » ne concorde avec rien : la marque est deja dans `brand` — refs #69."""

    def test_a_leading_brand_is_removed(self):
        from backend.food_import import strip_brand
        assert strip_brand("Auchan Pignons de Pin", "Auchan") == "pignon de pin"

    def test_a_multi_word_brand_is_removed(self):
        from backend.food_import import strip_brand
        assert strip_brand("Hello Fresh Boulgour", "Hello Fresh") == "boulgour"

    def test_a_brand_elsewhere_than_in_front_is_kept(self):
        from backend.food_import import strip_brand
        assert "auchan" in strip_brand("Sauce Auchan", "Auchan")

    def test_a_name_reduced_to_nothing_is_kept_whole(self):
        from backend.food_import import strip_brand
        assert strip_brand("Auchan", "Auchan") == "Auchan"

    def test_no_brand_leaves_the_name_alone(self):
        from backend.food_import import strip_brand
        assert strip_brand("Pignons de Pin", None) == "Pignons de Pin"


class TestLinkingRatchet:
    """Ratchet: every single product with a matching food must be linked — refs #69."""

    def _vault_with_pairs(self, tmp_path, pairs):
        root = tmp_path / "vault"
        (root / "generiques").mkdir(parents=True)
        (root / "marques").mkdir(parents=True)
        for slug, title in pairs:
            (root / "generiques" / f"{slug}.md").write_text(
                GENERIC.replace("title: Pain complet", f"title: {title}")
                       .replace("slug: pain-complet", f"slug: {slug}"),
                encoding="utf-8",
            )
        return root

    def test_all_singles_with_a_matching_food_are_linked(self, tmp_path):
        root = self._vault_with_pairs(tmp_path, [("oeuf", "Oeufs")])
        branded = BRANDED.replace(
            "title: Auchan Bio Plein Air Oeufs x12",
            "title: Auchan Oeufs x12",
        )
        (root / "marques" / "oeufs-a.md").write_text(branded, encoding="utf-8")
        (root / "marques" / "oeufs-b.md").write_text(
            branded.replace("slug: auchan-bio-plein-air-oeufs-x12",
                            "slug: auchan-oeufs-b-x6"),
            encoding="utf-8",
        )
        plan = build_records(root, {"auchan-bio-plein-air-oeufs-x12": "single",
                                    "auchan-oeufs-b-x6": "single"})
        unlinked = [p["name"] for p in plan.products if p["food_key"] is None]
        assert unlinked == [], f"unlinked singles: {unlinked}"

    def test_mixed_natures_only_singles_are_linked(self, tmp_path):
        root = self._vault_with_pairs(tmp_path, [("oeuf", "Oeufs")])
        branded = BRANDED.replace(
            "title: Auchan Bio Plein Air Oeufs x12",
            "title: Auchan Oeufs x12",
        )
        (root / "marques" / "single.md").write_text(branded, encoding="utf-8")
        (root / "marques" / "composite.md").write_text(
            branded.replace("slug: auchan-bio-plein-air-oeufs-x12",
                            "slug: lasagne-aux-oeufs"),
            encoding="utf-8",
        )
        plan = build_records(root, {"auchan-bio-plein-air-oeufs-x12": "single",
                                    "lasagne-aux-oeufs": "composite"})
        singles = [p for p in plan.products
                   if p.get("nature") == "single"]
        composites = [p for p in plan.products
                      if p.get("nature") == "composite"]
        assert all(s["food_key"] is not None for s in singles)
        assert all(c["food_key"] is None for c in composites)


class TestCompositeIsNeverLinked:
    """Un plat rattache a un ingredient donne les macros de l'ingredient au plat — refs #90."""

    def test_a_composite_is_not_linked_even_when_the_name_matches(self, tmp_path):
        root = make_vault(tmp_path)
        generic = root / "generiques" / "oeuf.md"
        generic.write_text(GENERIC.replace("title: Pain complet", "title: Oeufs")
                           .replace("slug: pain-complet", "slug: oeufs"), encoding="utf-8")
        plan = build_records(root, {"auchan-bio-plein-air-oeufs-x12": "composite"})
        assert plan.products[0]["food_key"] is None
        assert plan.products[0]["status"] == "a_rapprocher"

    def test_a_single_whose_name_designates_the_food_is_linked(self, tmp_path):
        root = make_vault(tmp_path)
        generic = root / "generiques" / "oeuf.md"
        generic.write_text(GENERIC.replace("title: Pain complet", "title: Oeufs")
                           .replace("slug: pain-complet", "slug: oeufs"), encoding="utf-8")
        sheet = root / "marques" / "oeufs.md"
        sheet.write_text(sheet.read_text(encoding="utf-8")
                         .replace("title: Auchan Bio Plein Air Oeufs x12",
                                  "title: Auchan Oeufs x12"), encoding="utf-8")
        plan = build_records(root, {"auchan-bio-plein-air-oeufs-x12": "single"})
        assert plan.products[0]["food_key"] == "oeuf"

    def test_a_qualifier_before_the_food_still_blocks_the_link(self, tmp_path):
        """« Auchan Bio Plein Air Oeufs » : marque retirée, le mot de tête reste « bio »."""
        root = make_vault(tmp_path)
        generic = root / "generiques" / "oeuf.md"
        generic.write_text(GENERIC.replace("title: Pain complet", "title: Oeufs")
                           .replace("slug: pain-complet", "slug: oeufs"), encoding="utf-8")
        plan = build_records(root, {"auchan-bio-plein-air-oeufs-x12": "single"})
        assert plan.products[0]["food_key"] is None
