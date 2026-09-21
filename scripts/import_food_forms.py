"""One-shot : fiches vault multi-formes → SQL food + food_form. Refs #99."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cooking_manager.ingredients import normalize_name
from cooking_manager.nutrition import Macros, parse_food_sheet
from cooking_manager.packaging import split_packaging

MACRO_FIELDS = ("kcal", "protein", "carbs", "fat")


def quote(value: object) -> str:
    if value is None or value == "":
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def number(value: float | None) -> str:
    return "NULL" if value is None else repr(float(value))


def sheets(root: Path) -> list[tuple[str, str, dict, dict[str, Macros]]]:
    found = []
    for path in sorted((root / "generiques").rglob("*.md")):
        if path.name.startswith("_"):
            continue
        fm, forms = parse_food_sheet(path.read_text(encoding="utf-8"))
        if len(forms) < 2:
            continue
        name, _ = split_packaging(str(fm.get("title") or path.stem))
        found.append((normalize_name(name), name, fm, forms))
    return found


def statements(root: Path) -> list[str]:
    out = []
    for key, name, fm, forms in sheets(root):
        out.append(
            "INSERT INTO food (key, name, category, kind, ciqual_code, source, verified_at)\n"
            f"VALUES ({quote(key)}, {quote(name)}, {quote(fm.get('categorie'))}, "
            f"{quote(fm.get('type_produit'))}, {quote(fm.get('ciqual_code'))}, "
            f"{quote(fm.get('source_macros'))}, {quote(fm.get('date_maj'))}::date)\n"
            "ON CONFLICT (key) DO UPDATE SET name = EXCLUDED.name,\n"
            "  category = COALESCE(EXCLUDED.category, food.category),\n"
            "  ciqual_code = COALESCE(EXCLUDED.ciqual_code, food.ciqual_code),\n"
            "  source = COALESCE(EXCLUDED.source, food.source);"
        )
        out.append(f"DELETE FROM food_form WHERE food_key = {quote(key)};")
        for label, macros in forms.items():
            values = ", ".join(number(getattr(macros, f)) for f in MACRO_FIELDS)
            out.append(
                "INSERT INTO food_form (food_key, label, kcal, protein, carbs, fat)\n"
                f"VALUES ({quote(key)}, {quote(label)}, {values});"
            )
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: import_food_forms.py <aliments-vérifiés/> [out.sql]", file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    lines = statements(root)
    sql = "BEGIN;\n" + "\n".join(lines) + "\nCOMMIT;\n"
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(sql, encoding="utf-8")
    else:
        sys.stdout.write(sql)
    print(f"{len(sheets(root))} aliments multi-formes", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
