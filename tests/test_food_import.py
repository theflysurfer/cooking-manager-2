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


class TestReport:
    def test_a_sheet_absent_from_the_base_is_reported(self, tmp_path):
        from backend.food_import import build_report
        report = build_report(make_vault(tmp_path), rows=[])
        assert report["missing"]
        assert report["imported"] == 0

    def test_a_macro_gap_is_reported_not_smoothed(self, tmp_path):
        from backend.food_import import build_report
        rows = [{"key": "pain complet", "macros_per_100g": {"kcal": 200}}]
        report = build_report(make_vault(tmp_path), rows=rows)
        assert report["macro_mismatch"]
        assert report["macro_mismatch"][0]["key"] == "pain complet"

    def test_person_constraints_found_in_sheets_are_listed(self, tmp_path):
        """« Léa : pas d'œufs durs » appartient à person.dislikes, pas à un aliment."""
        from backend.food_import import build_report
        root = make_vault(tmp_path)
        sheet = root / "marques" / "oeufs.md"
        sheet.write_text(sheet.read_text(encoding="utf-8")
                         + "\n- Lea : pas d'oeufs durs\n", encoding="utf-8")
        report = build_report(root, rows=[])
        assert report["person_constraints"]


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

    def test_a_dosage_line_is_not_a_person_constraint(self, tmp_path):
        """« Utilisation Julien : 40 g = 6.8 g glucides » est un dosage, pas une aversion."""
        from backend.food_import import build_report
        root = make_vault(tmp_path)
        sheet = root / "generiques" / "pain-complet.md"
        sheet.write_text(sheet.read_text(encoding="utf-8")
                         + "\n- **Utilisation Julien** : 40g = 6.8g glucides\n",
                         encoding="utf-8")
        assert build_report(root, rows=[])["person_constraints"] == []


class TestUnits:
    def test_usage_units_are_collected(self, tmp_path):
        plan = build_records(make_vault(tmp_path))
        assert {"unit": "pièce", "grams": 60.0} in [
            {"unit": u["unit"], "grams": u["grams"]} for u in plan.units
        ]
