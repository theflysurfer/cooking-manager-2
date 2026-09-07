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


class TestUnits:
    def test_usage_units_are_collected(self, tmp_path):
        plan = build_records(make_vault(tmp_path))
        assert {"unit": "pièce", "grams": 60.0} in [
            {"unit": u["unit"], "grams": u["grams"]} for u in plan.units
        ]
