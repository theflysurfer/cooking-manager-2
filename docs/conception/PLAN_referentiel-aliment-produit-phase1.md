# Référentiel aliment & produit — plan d'implémentation, phase 1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** faire exister en base les identités `food`, `food_unit` et `product`, peuplées depuis les 248 fiches du vault, et prouver leur équivalence — sans qu'aucun consommateur ne change de source.

**Architecture:** trois modules purs et testables sans DB (extraction du conditionnement, lecture des unités d'usage, signaux de rapprochement), puis le schéma, l'import, et un rapport d'équivalence qui bloque la suite. `nutrition.py`, le garde-manger et le MCP continuent de lire le vault pendant toute la phase 1 : rien ne casse si l'import est faux, et le rapport le dira.

**Tech Stack:** Python 3.13, FastAPI, asyncpg, PostgreSQL (conteneur `postgresql-shared` sur srv759970), pytest.

**Spec:** `docs/conception/SPEC_referentiel-aliment-produit.md`

## Global Constraints

- **Zéro commentaire dans le code** (`#`, `//`, `/* */`) — une docstring d'une ligne est permise ; le pourquoi va en ADR. Gate bloquant : `python ~/.claude/skills/julien-audit-comments/check_comments.py . --ci`
- **Identifiants en anglais**, texte utilisateur en français.
- **Gates avant tout commit** : `python -m ruff check cooking_manager/ backend/ tests/` · `python -m pyright` · `python -m pytest tests/`
- **Toute colonne ajoutée à un `CREATE TABLE` va AUSSI dans `MIGRATIONS_SQL`** — le VPS a déjà les tables.
- **Jamais de `localhost`** : l'API se joint par `ssh srv759970 'curl -s localhost:8795/...'`.
- **Tests unitaires sans DB ni réseau.** Les tests qui frappent l'API réelle sont marqués `e2e` et opt-in.
- **Pas d'hypothèse silencieuse** : une valeur non déductible est déclarée (`None` + motif), jamais devinée.

## Structure des fichiers

| Fichier | Responsabilité |
|---|---|
| `cooking_manager/packaging.py` *(neuf)* | séparer un conditionnement d'un nom — pur |
| `cooking_manager/food_units.py` *(neuf)* | lire les unités d'usage d'une fiche — pur |
| `cooking_manager/matching.py` *(neuf)* | les quatre signaux et leur pouvoir de réfutation — pur |
| `backend/db.py` *(modifié)* | `food`, `food_unit`, `product` dans `SCHEMA_SQL` **et** `MIGRATIONS_SQL` |
| `backend/food_import.py` *(neuf)* | vault → base, et le rapport d'équivalence |
| `backend/app.py` *(modifié)* | `POST /api/food/import`, `GET /api/food/report` |
| `tests/test_packaging.py`, `tests/test_food_units.py`, `tests/test_matching.py`, `tests/test_food_import.py` *(neufs)* | un test par piège |

---

### Task 1: Séparer le conditionnement du nom

Le slug `auchan-bio-plein-air-oeufs-x12` et la ligne de ticket `Oeufs plein air x10` portent leur conditionnement dans leur nom. C'est ce qui a créé un doublon d'aliment le 2026-08-19.

**Files:**
- Create: `cooking_manager/packaging.py`
- Test: `tests/test_packaging.py`

**Interfaces:**
- Consumes: rien.
- Produces: `split_packaging(name: str) -> tuple[str, Pack]` et `Pack(count: float | None, size_value: float | None, size_unit: str | None)`.

- [ ] **Step 1: Write the failing test**

```python
from cooking_manager.packaging import Pack, split_packaging


class TestCount:
    def test_x_suffix_leaves_the_name_clean(self):
        name, pack = split_packaging("Auchan Bio Plein Air Oeufs x12")
        assert name == "Auchan Bio Plein Air Oeufs"
        assert pack.count == 12

    def test_uppercase_x_too(self):
        assert split_packaging("Oeufs plein air X10")[1].count == 10

    def test_leading_count(self):
        name, pack = split_packaging("2 boîtes de thon listao")
        assert pack.count == 2
        assert name == "thon listao"


class TestSize:
    def test_weight_in_the_name(self):
        name, pack = split_packaging("Comté Juraflore AOP 250 g")
        assert name == "Comté Juraflore AOP"
        assert (pack.size_value, pack.size_unit) == (250.0, "g")

    def test_pack_of_size(self):
        name, pack = split_packaging("Poêlée méditerranéenne sachet 750 g")
        assert name == "Poêlée méditerranéenne"
        assert (pack.count, pack.size_value, pack.size_unit) == (1.0, 750.0, "g")

    def test_volume(self):
        assert split_packaging("Lait de coco 400 ml")[1].size_unit == "ml"


class TestLeaveAlone:
    def test_a_number_that_belongs_to_the_food(self):
        """« 5 baies » et « 4 fromages » nomment l'aliment, pas son emballage."""
        name, pack = split_packaging("Poivre 5 baies")
        assert name == "Poivre 5 baies"
        assert pack == Pack(None, None, None)

    def test_percentage_is_not_a_size(self):
        name, pack = split_packaging("Chocolat noir 70% cacao")
        assert name == "Chocolat noir 70% cacao"
        assert pack.size_value is None

    def test_plain_name_untouched(self):
        assert split_packaging("Comté") == ("Comté", Pack(None, None, None))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_packaging.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cooking_manager.packaging'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Séparer ce qu'un aliment EST de la façon dont il est vendu."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .ingredients import UNIT_ALIASES

_UNIT_WORDS = sorted(
    (v for variants in UNIT_ALIASES.values() for v in variants),
    key=len,
    reverse=True,
)
_UNIT_LOOKUP = {v.lower(): canonical
                for canonical, variants in UNIT_ALIASES.items()
                for v in variants}

_PACK_WORDS = ("sachet", "sachets", "boîte", "boîtes", "boite", "boites",
               "paquet", "paquets", "pot", "pots", "brique", "briques",
               "barquette", "barquettes", "bocal", "bocaux")

_COUNT_SUFFIX = re.compile(r"\s*[xX×]\s*(\d+)\s*$")
_LEADING_COUNT = re.compile(
    r"^\s*(\d+)\s+(" + "|".join(_PACK_WORDS) + r")\s+(?:de\s+|d')?",
    re.IGNORECASE,
)
_PACK_SIZE = re.compile(
    r"\s*(?:(" + "|".join(_PACK_WORDS) + r")\s+)?"
    r"(\d+(?:[.,]\d+)?)\s*(" + "|".join(re.escape(u) for u in _UNIT_WORDS) + r")\s*$",
    re.IGNORECASE,
)
_PERCENT = re.compile(r"\d+\s*%")


@dataclass(frozen=True)
class Pack:
    """Comment un aliment est vendu — jamais ce qu'il est."""
    count: float | None = None
    size_value: float | None = None
    size_unit: str | None = None


def split_packaging(name: str) -> tuple[str, Pack]:
    """Nom brut → (nom sans conditionnement, conditionnement lu)."""
    if not name:
        return name, Pack()

    count: float | None = None
    size_value: float | None = None
    size_unit: str | None = None

    rest = name.strip()

    m = _COUNT_SUFFIX.search(rest)
    if m:
        count = float(m.group(1))
        rest = rest[: m.start()].strip()

    m = _LEADING_COUNT.match(rest)
    if m:
        count = float(m.group(1))
        rest = rest[m.end():].strip()

    if not _PERCENT.search(rest):
        m = _PACK_SIZE.search(rest)
        if m and m.group(3).lower() in _UNIT_LOOKUP:
            size_value = float(m.group(2).replace(",", "."))
            size_unit = _UNIT_LOOKUP[m.group(3).lower()]
            if m.group(1):
                count = count or 1.0
            rest = rest[: m.start()].strip()

    return (rest or name.strip()), Pack(count, size_value, size_unit)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_packaging.py -q`
Expected: PASS — 9 tests.

Si `test_a_number_that_belongs_to_the_food` échoue, c'est que `5 baies` a été lu comme un conditionnement : `baies` ne doit pas figurer dans `UNIT_ALIASES`. Vérifier avec `python -c "from cooking_manager.ingredients import UNIT_ALIASES; print(UNIT_ALIASES.keys())"` avant de modifier la regex.

- [ ] **Step 5: Gates + commit**

```bash
python -m ruff check cooking_manager/ tests/
python -m pyright
python -m pytest tests/ -q
python ~/.claude/skills/julien-audit-comments/check_comments.py cooking_manager/packaging.py
git add cooking_manager/packaging.py tests/test_packaging.py
git commit -m "feat(food): le conditionnement sort du nom

refs #82"
```

---

### Task 2: Lire les unités d'usage d'une fiche

Les fiches portent « Par œuf (~60 g) » — c'est ce que #80 attend pour convertir une pièce. Le gramme ne couvre que 38 % des lignes d'ingrédients : il faut plusieurs unités par aliment.

**Files:**
- Create: `cooking_manager/food_units.py`
- Test: `tests/test_food_units.py`

**Interfaces:**
- Consumes: `Pack` de la Task 1 (non requis ici, mais même vocabulaire d'unité).
- Produces: `read_food_units(text: str) -> list[FoodUnit]` et `FoodUnit(unit: str, grams: float)`.

- [ ] **Step 1: Write the failing test**

```python
from cooking_manager.food_units import FoodUnit, read_food_units

SHEET = """---
title: Auchan Bio Plein Air Oeufs
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


class TestRead:
    def test_reads_the_unit_and_its_weight(self):
        assert read_food_units(SHEET) == [FoodUnit("pièce", 60.0)]

    def test_named_unit_is_kept(self):
        sheet = SHEET.replace("Par oeuf (~60g)", "Par gousse (~5 g)")
        assert read_food_units(sheet) == [FoodUnit("gousse", 5.0)]

    def test_several_units(self):
        sheet = SHEET + "\n## Par tranche (~30 g)\n\n| x | y |\n"
        assert read_food_units(sheet) == [FoodUnit("pièce", 60.0), FoodUnit("tranche", 30.0)]

    def test_scoop(self):
        sheet = SHEET.replace("Par oeuf (~60g)", "Par scoop (30 g)")
        assert read_food_units(sheet) == [FoodUnit("scoop", 30.0)]


class TestRefuse:
    def test_no_section_yields_nothing(self):
        assert read_food_units("## Macros pour 100 g\n\n| a | b |\n") == []

    def test_a_section_without_weight_is_not_guessed(self):
        """« Par portion » sans grammage ne donne rien — pas d'hypothèse."""
        assert read_food_units("## Par portion\n\n| a | b |\n") == []

    def test_the_100g_section_is_not_a_unit(self):
        assert FoodUnit("pièce", 100.0) not in read_food_units("## Macros pour 100 g\n")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_food_units.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cooking_manager.food_units'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Les unités dans lesquelles un aliment se compte, avec leur poids."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .ingredients import UNIT_ALIASES, normalize_name

_UNIT_LOOKUP = {v.lower(): canonical
                for canonical, variants in UNIT_ALIASES.items()
                for v in variants}

_COUNTED_AS_PIECE = ("oeuf", "œuf", "unite", "unité", "fruit", "piece", "pièce")

_SECTION = re.compile(
    r"^##\s+Par\s+([^(\n]+?)\s*\(\s*~?\s*(\d+(?:[.,]\d+)?)\s*(g|kg|ml|cl|l)\s*\)",
    re.IGNORECASE | re.MULTILINE,
)

_TO_GRAMS = {"g": 1.0, "kg": 1000.0, "ml": 1.0, "cl": 10.0, "l": 1000.0}


@dataclass(frozen=True)
class FoodUnit:
    unit: str
    grams: float


def read_food_units(text: str) -> list[FoodUnit]:
    """Fiche markdown → unités d'usage nommées, avec leur poids."""
    units: list[FoodUnit] = []
    for label, value, unit in _SECTION.findall(text or ""):
        grams = float(value.replace(",", ".")) * _TO_GRAMS[unit.lower()]
        units.append(FoodUnit(_canonical_unit(label), grams))
    return units


def _canonical_unit(label: str) -> str:
    key = normalize_name(label.strip())
    if key in _UNIT_LOOKUP:
        return _UNIT_LOOKUP[key]
    if any(word in key for word in _COUNTED_AS_PIECE):
        return "pièce"
    return key
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_food_units.py -q`
Expected: PASS — 7 tests.

- [ ] **Step 5: Mesurer la couverture réelle sur le vault**

```bash
python -c "
from pathlib import Path
from cooking_manager.food_units import read_food_units
root = Path(r'E:/Dr2/Dropbox/JULIEN/Obsidian/vault/Noyau/Coaches/Coach Nutrition/aliments-vérifiés')
sheets = [p for p in root.rglob('*.md') if not p.name.startswith('_')]
found = [(p.stem, read_food_units(p.read_text(encoding='utf-8'))) for p in sheets]
with_units = [f for f in found if f[1]]
print(len(sheets), 'fiches |', len(with_units), 'portent au moins une unité d usage')
for name, us in with_units[:15]: print(' ', name, us)
"
```

Noter le chiffre dans le message de commit : c'est la mesure qui dira, en Task 6, combien d'aliments savent convertir une pièce.

- [ ] **Step 6: Gates + commit**

```bash
python -m ruff check cooking_manager/ tests/
python -m pyright
python -m pytest tests/ -q
git add cooking_manager/food_units.py tests/test_food_units.py
git commit -m "feat(food): les unites d usage d un aliment, lues dans sa fiche

refs #80"
```

---

### Task 3: Les signaux de rapprochement

Un nom seul ne peut ni rapprocher ni réfuter. Un signal peut réfuter seul ; aucun ne peut conclure seul.

**Files:**
- Create: `cooking_manager/matching.py`
- Test: `tests/test_matching.py`

**Interfaces:**
- Consumes: rien.
- Produces: `compare(candidate: Signals, target: Signals) -> Match` où
  `Signals(name: str, grams: float | None, price_per_kg: float | None, brand: str | None)`
  et `Match(verdict: str, reasons: list[str])` avec `verdict ∈ {"propose", "refuse", "unsure"}`.

- [ ] **Step 1: Write the failing test**

```python
from cooking_manager.matching import Match, Signals, compare


def sig(name, grams=None, price=None, brand=None):
    return Signals(name=name, grams=grams, price_per_kg=price, brand=brand)


class TestRefutation:
    def test_weight_refutes(self):
        """Un pot de 10 g et un sachet de 500 g ne sont pas le même usage."""
        m = compare(sig("origan", grams=10), sig("origan", grams=500))
        assert m.verdict == "refuse"
        assert any("poids" in r for r in m.reasons)

    def test_price_refutes_on_an_order_of_magnitude(self):
        m = compare(sig("curcuma", price=34.0), sig("safran", price=3000.0))
        assert m.verdict == "refuse"

    def test_a_different_brand_never_refutes_the_food(self):
        m = compare(sig("comté", brand="Juraflore"), sig("comté", brand="Entremont"))
        assert m.verdict == "propose"


class TestMuteSignals:
    def test_a_zero_price_is_mute_not_favourable(self):
        """`price` vaut 0.0 dans les résultats Auchan : un parsing manqué."""
        m = compare(sig("origan", price=0.0), sig("origan", price=42.0))
        assert m.verdict == "unsure"
        assert any("prix" in r for r in m.reasons)

    def test_a_missing_weight_does_not_refute(self):
        assert compare(sig("comté"), sig("comté", grams=250)).verdict == "propose"


class TestNameAlone:
    def test_different_names_never_propose(self):
        assert compare(sig("riz"), sig("vinaigre de riz")).verdict == "refuse"

    def test_a_qualifier_still_concords(self):
        assert compare(sig("origan"), sig("origan séché")).verdict == "propose"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_matching.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cooking_manager.matching'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Rapprocher deux libellés : un signal peut réfuter seul, aucun ne conclut seul."""

from __future__ import annotations

from dataclasses import dataclass, field

from .ingredients import normalize_name
from .pantry import _contains_words, _content_words

WEIGHT_RATIO = 5.0
PRICE_RATIO = 10.0

PROPOSE = "propose"
REFUSE = "refuse"
UNSURE = "unsure"


@dataclass(frozen=True)
class Signals:
    name: str
    grams: float | None = None
    price_per_kg: float | None = None
    brand: str | None = None


@dataclass
class Match:
    verdict: str
    reasons: list[str] = field(default_factory=list)


def compare(candidate: Signals, target: Signals) -> Match:
    """Deux jeux de signaux → un verdict motivé."""
    reasons: list[str] = []
    a, b = normalize_name(candidate.name), normalize_name(target.name)

    concords = a == b or _contains_words(b, a) or _contains_words(a, b) \
        or _content_words(a) <= _content_words(b) or _content_words(b) <= _content_words(a)
    if not concords:
        return Match(REFUSE, [f"les noms ne concordent pas : « {a} » / « {b} »"])

    if _refutes(candidate.grams, target.grams, WEIGHT_RATIO):
        reasons.append(f"poids incompatibles : {candidate.grams} g / {target.grams} g")
        return Match(REFUSE, reasons)

    mute = False
    if _is_mute(candidate.price_per_kg) or _is_mute(target.price_per_kg):
        reasons.append("prix absent ou nul — critère muet, jamais favorable")
        mute = True
    elif _refutes(candidate.price_per_kg, target.price_per_kg, PRICE_RATIO):
        reasons.append(
            f"prix au kilo incompatibles : {candidate.price_per_kg} / {target.price_per_kg}")
        return Match(REFUSE, reasons)

    return Match(UNSURE if mute else PROPOSE, reasons)


def _is_mute(value: float | None) -> bool:
    return value is None or value <= 0


def _refutes(a: float | None, b: float | None, ratio: float) -> bool:
    if _is_mute(a) or _is_mute(b):
        return False
    high, low = max(a, b), min(a, b)  # type: ignore[type-var]
    return high / low >= ratio
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_matching.py -q`
Expected: PASS — 7 tests.

Si `test_a_missing_weight_does_not_refute` échoue, c'est que l'absence a été traitée comme une valeur : `_is_mute` doit court-circuiter avant tout calcul de ratio.

- [ ] **Step 5: Gates + commit**

```bash
python -m ruff check cooking_manager/ tests/
python -m pyright
python -m pytest tests/ -q
git add cooking_manager/matching.py tests/test_matching.py
git commit -m "feat(food): quatre signaux, dont trois peuvent refuter seuls

refs #82"
```

---

### Task 4: Le schéma

**Files:**
- Modify: `backend/db.py` — `SCHEMA_SQL` **et** `MIGRATIONS_SQL`

**Interfaces:**
- Consumes: rien.
- Produces: les tables `food`, `food_unit`, `product` ; contrainte `product.food_key → food.key`.

- [ ] **Step 1: Ajouter les tables à `SCHEMA_SQL`**

À placer après la définition de `pantry_alias` :

```sql
CREATE TABLE IF NOT EXISTS food (
    key             TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    category        TEXT,
    kind            TEXT,
    ciqual_code     TEXT,
    macros_per_100g JSONB,
    conservation    TEXT,
    source          TEXT,
    verified_at     DATE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS food_unit (
    food_key   TEXT NOT NULL REFERENCES food(key) ON DELETE CASCADE,
    unit       TEXT NOT NULL,
    grams      REAL NOT NULL,
    source     TEXT,
    PRIMARY KEY (food_key, unit)
);

CREATE TABLE IF NOT EXISTS product (
    id              SERIAL PRIMARY KEY,
    food_key        TEXT REFERENCES food(key) ON DELETE SET NULL,
    name            TEXT NOT NULL,
    brand           TEXT,
    ean             TEXT,
    store           TEXT,
    store_ref       TEXT,
    pack_count      REAL,
    pack_size_value REAL,
    pack_size_unit  TEXT,
    nutriscore      TEXT,
    macros_per_100g JSONB,
    last_price      REAL,
    price_per_kg    REAL,
    price_seen_at   DATE,
    status          TEXT DEFAULT 'linked',
    source          TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (store, store_ref)
);

CREATE INDEX IF NOT EXISTS product_food_idx ON product(food_key);
CREATE INDEX IF NOT EXISTS product_ean_idx ON product(ean);
```

`status` vaut `linked` ou `a_rapprocher` — c'est le marqueur visible de la spec : jamais d'état intermédiaire silencieux.

- [ ] **Step 2: Répéter dans `MIGRATIONS_SQL`**

Le VPS a déjà les tables ; `SCHEMA_SQL` n'y crée que ce qui manque, mais toute évolution ultérieure d'une colonne devra passer par `MIGRATIONS_SQL`. Ajouter, à la fin :

```sql
ALTER TABLE product ADD COLUMN IF NOT EXISTS price_seen_at DATE;
ALTER TABLE product ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'linked';
```

- [ ] **Step 3: Appliquer et vérifier sur le VPS**

```bash
ssh srv759970 'cd /opt/cooking-manager-2 && git pull && .venv/bin/pip install -q . && sudo systemctl restart cooking-manager'
ssh srv759970 'docker exec postgresql-shared psql -U cooking -d cooking_manager -c "\d food"'
ssh srv759970 'docker exec postgresql-shared psql -U cooking -d cooking_manager -c "\d product"'
```

Attendu : les trois tables existent, `product.food_key` porte bien sa clé étrangère.

⚠️ `ON DELETE SET NULL` sur `product.food_key`, jamais `CASCADE` : supprimer un aliment ne doit pas effacer l'historique des produits achetés. C'est la leçon des 7 alias emportés le 2026-09-07.

- [ ] **Step 4: Commit**

```bash
git add backend/db.py
git commit -m "feat(db): tables food, food_unit et product

refs #69, #82"
```

---

### Task 5: Importer les fiches

**Files:**
- Create: `backend/food_import.py`
- Modify: `backend/app.py` — route `POST /api/food/import`
- Test: `tests/test_food_import.py`

**Interfaces:**
- Consumes: `split_packaging` (Task 1), `read_food_units` (Task 2), `parse_food_sheet` et `normalize_name` (existants).
- Produces: `build_records(root: Path) -> ImportPlan` avec
  `ImportPlan(foods: list[dict], units: list[dict], products: list[dict], skipped: list[dict])`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_food_import.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.food_import'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Vault `aliments-vérifiés/` → enregistrements food, food_unit et product."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cooking_manager.food_units import read_food_units
from cooking_manager.ingredients import normalize_name
from cooking_manager.matching import PROPOSE, Signals, compare
from cooking_manager.nutrition import parse_food_sheet
from cooking_manager.packaging import split_packaging


@dataclass
class ImportPlan:
    foods: list[dict] = field(default_factory=list)
    units: list[dict] = field(default_factory=list)
    products: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)


def build_records(root: Path) -> ImportPlan:
    """Lit le vault et prépare les lignes, sans écrire en base."""
    plan = ImportPlan()
    if not root.is_dir():
        return plan

    for path in sorted(root.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        fm, forms = parse_food_sheet(text)
        title = str(fm.get("title") or path.stem)
        is_branded = "marques" in path.parts or bool(fm.get("marque"))
        clean_name, pack = split_packaging(title)

        if not forms:
            plan.skipped.append({"path": str(path), "reason": "aucune macro pour 100 g"})
            continue

        macros = _first_form(forms)

        if is_branded:
            plan.products.append({
                "name": clean_name,
                "brand": fm.get("marque"),
                "pack_count": pack.count,
                "pack_size_value": pack.size_value,
                "pack_size_unit": pack.size_unit,
                "nutriscore": fm.get("nutriscore"),
                "macros_per_100g": macros,
                "food_key": None,
                "status": "a_rapprocher",
                "source": "vault",
                "_units": [{"unit": u.unit, "grams": u.grams} for u in read_food_units(text)],
                "_kind": fm.get("type_produit"),
            })
            continue

        key = normalize_name(clean_name)
        plan.foods.append({
            "key": key,
            "name": clean_name,
            "category": fm.get("categorie"),
            "kind": fm.get("type_produit"),
            "ciqual_code": fm.get("ciqual_code"),
            "macros_per_100g": macros,
            "source": fm.get("source_macros"),
            "verified_at": fm.get("date_maj"),
        })
        for unit in read_food_units(text):
            plan.units.append({"food_key": key, "unit": unit.unit,
                               "grams": unit.grams, "source": "fiche"})

    _link_products(plan)
    return plan


def _first_form(forms: dict) -> dict:
    name, macros = next(iter(forms.items()))
    return {"form": name, **_as_dict(macros)}


def _as_dict(macros) -> dict:
    return {k: getattr(macros, k) for k in ("kcal", "protein", "carbs", "fat")}


def _link_products(plan: ImportPlan) -> None:
    """Rattache chaque produit à un aliment quand aucun signal ne s'y oppose."""
    by_key = {f["key"]: f for f in plan.foods}
    for product in plan.products:
        candidate = Signals(name=product["name"], grams=product.get("pack_size_value"),
                            brand=product.get("brand"))
        for key, food in by_key.items():
            if compare(candidate, Signals(name=food["name"])).verdict != PROPOSE:
                continue
            product["food_key"] = key
            product["status"] = "linked"
            for unit in product.pop("_units", []):
                plan.units.append({"food_key": key, "unit": unit["unit"],
                                   "grams": unit["grams"], "source": "produit"})
            break
        product.pop("_units", None)
        product.pop("_kind", None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_food_import.py -q`
Expected: PASS — 6 tests.

- [ ] **Step 5: Ajouter la route d'import**

Dans `backend/app.py`, à la suite des routes `pantry` :

```python
@app.post("/api/food/import")
async def import_food(dry_run: bool = True):
    """Vault `aliments-vérifiés/` → tables food, food_unit, product."""
    from backend.food_import import build_records, write_records

    plan = build_records(Path(FOOD_BASE_PATH))
    counts = {"foods": len(plan.foods), "units": len(plan.units),
              "products": len(plan.products), "skipped": len(plan.skipped)}
    if dry_run:
        return {"dry_run": True, "counts": counts, "skipped": plan.skipped[:20]}

    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        written = await write_records(conn, plan)
    return {"dry_run": False, "counts": counts, "written": written,
            "skipped": plan.skipped[:20]}
```

`FOOD_BASE_PATH` existe déjà dans `backend/app.py` pour `nutrition.py` — le réutiliser, ne pas en créer un second.

- [ ] **Step 6: Écrire `write_records`**

```python
async def write_records(conn, plan: ImportPlan) -> dict:
    """Upsert idempotent : rejouer l'import ne duplique rien."""
    for food in plan.foods:
        await conn.execute(
            """INSERT INTO food (key, name, category, kind, ciqual_code,
                                 macros_per_100g, source, verified_at)
               VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8::date)
               ON CONFLICT (key) DO UPDATE SET
                 name = EXCLUDED.name, category = EXCLUDED.category,
                 kind = EXCLUDED.kind, ciqual_code = EXCLUDED.ciqual_code,
                 macros_per_100g = EXCLUDED.macros_per_100g,
                 source = EXCLUDED.source, verified_at = EXCLUDED.verified_at""",
            food["key"], food["name"], food["category"], food["kind"],
            food["ciqual_code"], json.dumps(food["macros_per_100g"]),
            food["source"], food["verified_at"])

    for unit in plan.units:
        await conn.execute(
            """INSERT INTO food_unit (food_key, unit, grams, source)
               VALUES ($1,$2,$3,$4)
               ON CONFLICT (food_key, unit) DO UPDATE SET grams = EXCLUDED.grams""",
            unit["food_key"], unit["unit"], unit["grams"], unit["source"])

    for product in plan.products:
        await conn.execute(
            """INSERT INTO product (food_key, name, brand, pack_count,
                                    pack_size_value, pack_size_unit, nutriscore,
                                    macros_per_100g, status, source, store, store_ref)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11,$12)
               ON CONFLICT (store, store_ref) DO UPDATE SET
                 food_key = EXCLUDED.food_key, status = EXCLUDED.status""",
            product["food_key"], product["name"], product["brand"],
            product["pack_count"], product["pack_size_value"],
            product["pack_size_unit"], product["nutriscore"],
            json.dumps(product["macros_per_100g"]), product["status"],
            product["source"], "vault", product["name"])

    return {"foods": len(plan.foods), "units": len(plan.units),
            "products": len(plan.products)}
```

- [ ] **Step 7: Déployer et lancer en dry-run**

```bash
ssh srv759970 'cd /opt/cooking-manager-2 && git pull && .venv/bin/pip install -q . && sudo systemctl restart cooking-manager'
ssh srv759970 'curl -s -X POST "localhost:8795/api/food/import?dry_run=true" | python3 -m json.tool'
```

Attendu : ~69 `foods`, ~179 `products`, et une liste `skipped` **lisible** — chaque fiche écartée porte son motif. Une fiche sans macros pour 100 g est écartée, jamais importée avec des zéros.

- [ ] **Step 8: Gates + commit**

```bash
python -m ruff check cooking_manager/ backend/ tests/
python -m pyright
python -m pytest tests/ -q
python ~/.claude/skills/julien-audit-comments/check_comments.py . --ci
git add backend/food_import.py backend/app.py tests/test_food_import.py
git commit -m "feat(food): importer les fiches du vault en base

refs #69, #82"
```

---

### Task 6: Le rapport d'équivalence

C'est l'étape qui protège : une migration qui ne se prouve pas est une perte silencieuse. **Aucune bascule de consommateur ne commence avant que ce rapport soit vert.**

**Files:**
- Modify: `backend/food_import.py` — `build_report`
- Modify: `backend/app.py` — route `GET /api/food/report`
- Test: `tests/test_food_import.py` (classe `TestReport`)

**Interfaces:**
- Consumes: `build_records` (Task 5), `load_food_base` (existant).
- Produces: `build_report(root: Path, rows: list[dict]) -> dict` avec les clés
  `total_sheets`, `imported`, `missing`, `macro_mismatch`, `unlinked_products`, `person_constraints`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_food_import.py::TestReport -q`
Expected: FAIL — `ImportError: cannot import name 'build_report'`

- [ ] **Step 3: Write minimal implementation**

```python
_PERSON_NAMES = ("julien", "clemence", "clémence", "lea", "léa", "titouan")


def build_report(root: Path, rows: list[dict]) -> dict:
    """Compare le vault à ce qui est en base — sans rien corriger."""
    plan = build_records(root)
    by_key = {r["key"]: r for r in rows}

    missing = [f["key"] for f in plan.foods if f["key"] not in by_key]
    mismatch = []
    for food in plan.foods:
        stored = by_key.get(food["key"])
        if not stored:
            continue
        expected = (food["macros_per_100g"] or {}).get("kcal")
        actual = (stored.get("macros_per_100g") or {}).get("kcal")
        if expected is not None and actual is not None and abs(expected - actual) > 1:
            mismatch.append({"key": food["key"], "vault": expected, "base": actual})

    constraints = []
    for path in sorted(root.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            low = line.lower()
            if any(name in low for name in _PERSON_NAMES) and ":" in line:
                constraints.append({"sheet": path.stem, "line": line.strip()})

    return {
        "total_sheets": len(plan.foods) + len(plan.products),
        "imported": len(by_key),
        "missing": missing,
        "macro_mismatch": mismatch,
        "unlinked_products": [p["name"] for p in plan.products
                              if p["status"] == "a_rapprocher"],
        "person_constraints": constraints,
        "skipped": plan.skipped,
    }
```

- [ ] **Step 4: Ajouter la route**

```python
@app.get("/api/food/report")
async def food_report():
    """Le vault et la base disent-ils la même chose ?"""
    from backend.food_import import build_report

    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT key, macros_per_100g FROM food")
    return build_report(Path(FOOD_BASE_PATH), [dict(r) for r in rows])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_food_import.py -q`
Expected: PASS — 9 tests.

- [ ] **Step 6: Importer pour de vrai, puis lire le rapport**

```bash
ssh srv759970 'cd /opt/cooking-manager-2 && git pull && .venv/bin/pip install -q . && sudo systemctl restart cooking-manager'
ssh srv759970 'curl -s -X POST "localhost:8795/api/food/import?dry_run=false" | python3 -m json.tool'
ssh srv759970 'curl -s "localhost:8795/api/food/report" | python3 -c "
import sys, json
r = json.load(sys.stdin)
print(\"fiches:\", r[\"total_sheets\"], \"| en base:\", r[\"imported\"])
print(\"manquantes:\", len(r[\"missing\"]), \"| ecarts de macros:\", len(r[\"macro_mismatch\"]))
print(\"produits non rattaches:\", len(r[\"unlinked_products\"]))
print(\"contraintes de personne a deplacer:\", len(r[\"person_constraints\"]))
for c in r[\"person_constraints\"][:10]: print(\"  \", c[\"sheet\"], \"|\", c[\"line\"][:70])
"'
```

**Critère de sortie de la phase 1** — le rapport doit rendre :
- `missing` **vide** ;
- `macro_mismatch` **vide** ;
- `unlinked_products` : une liste **nommée**, chaque produit non rattaché étant un choix à faire, pas un oubli ;
- `person_constraints` : la liste des lignes à déplacer vers `person.dislikes` (phase 2).

Un `missing` ou un `macro_mismatch` non vide **bloque** : ne pas passer à la phase 2, corriger l'import.

- [ ] **Step 7: Gates + commit**

```bash
python -m ruff check cooking_manager/ backend/ tests/
python -m pyright
python -m pytest tests/ -q
python ~/.claude/skills/julien-audit-comments/check_comments.py . --ci
git add backend/food_import.py backend/app.py tests/test_food_import.py
git commit -m "feat(food): le rapport d equivalence, porte de la bascule

refs #69"
```

---

## Hors périmètre de la phase 1, et déclaré comme tel

Trois éléments de la spec ne sont **pas** implémentés ici, et aucun n'est oublié :

| Élément de la spec | Pourquoi pas maintenant |
|---|---|
| **Étage 4 par modèle** (vérification sémantique proposée à Julien) | la Task 3 livre les signaux et leur pouvoir de réfutation, qui sont la partie testable. L'appel à un modèle et l'écran de validation viennent avec les outils MCP, en phase 2 |
| **Rapprochement ticket → catalogue Auchan** | dépend d'une session Auchan vivante (morte au 2026-09-07, mcp-vps#184). Un chemin qu'on ne peut pas éprouver ne s'écrit pas d'avance |
| **Axe `units` dans l'ontologie** | c'est le sous-projet 2, avec les niveaux et la conservation des rayons — et il touche `ontology-manager`, donc deux dépôts |

Les cinq tables d'unités qui coexistent aujourd'hui (`UNIT_ALIASES`, `_TO_BASE`,
`_SPOON_SCALE`, `GRAMS_PER_UNIT`, `MEASURED/COUNTABLE/DOSE_UNITS`) **ne sont pas
touchées** en phase 1. Ce plan en ajoute une lecture (`food_units.py` réutilise
`UNIT_ALIASES`), il n'en crée pas une sixième.

## Ce que la phase 1 ne fait pas

Aucun consommateur ne change de source. `nutrition.py`, le garde-manger, `purchase.py` et le MCP continuent de lire ce qu'ils lisaient : si l'import est faux, le rapport le dit et rien n'est cassé.

La phase 2 — dont le plan s'écrira **après** que le rapport soit vert — porte :

1. les contraintes de personne déplacées des fiches vers `person.dislikes` (liste produite par le rapport) ;
2. `nutrition.py` sur la DB, avec non-régression des macros d'un menu déjà calculé ;
3. `purchase.py` utilisant `food_unit` pour convertir une pièce ;
4. les outils MCP `food_search` / `food_detail` / `food_upsert` / `product_upsert` / `product_link` ;
5. la base legacy `logs/aliments/` — résorbée ou déclarée morte ;
6. l'archivage des fiches et le **retrait du code de lecture** du vault.
