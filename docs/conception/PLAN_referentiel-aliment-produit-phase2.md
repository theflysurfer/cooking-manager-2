# Référentiel aliment & produit — plan d'implémentation, phase 2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** faire lire la DB à tous les consommateurs du référentiel aliment, prouver
qu'aucune macro ne bouge, puis retirer le code de lecture du vault.

**Architecture:** la phase 1 a peuplé `food`, `food_unit` et `product` sans que rien
ne bascule. La phase 2 substitue la **source** sans toucher le **moteur** :
`load_food_base()` rend un `dict[str, FoodEntry]`, on écrit un lecteur DB qui rend
le même type, et `merge_sources`, `match_entry`, `macros_for` et `recipe_macros` ne
changent pas d'une ligne. Une non-régression sur un menu réel garde la porte entre
la bascule et la suppression.

**Tech Stack:** Python 3.13, FastAPI, asyncpg, PostgreSQL (`postgresql-shared` sur
srv759970), pytest, FastMCP v3.4+.

**Spec:** `docs/conception/SPEC_referentiel-aliment-produit.md`
**Décisions qui s'appliquent :** [ADR 0010](../decisions/0010-le-vault-cuisine-est-decommissionne-la-db-fait-foi.md) · [ADR 0011](../decisions/0011-un-import-ne-tranche-pas-il-declare.md)

## État à l'entrée (mesuré le 2026-09-07)

| Fait | Valeur |
|---|---|
| Rapport d'équivalence | `missing` 0 · `macro_mismatch` 0 · `collisions` 0 |
| En base | 61 `food` · 170 `product` (10 `linked`, 160 `a_rapprocher`) · **0** `food_unit` |
| Fiches écartées, avec motif | 16 |
| Contraintes de personne candidates | 22 |
| Base legacy `logs/aliments/` | 73 fiches |

## Global Constraints

- **Zéro commentaire dans le code** (`#`, `//`, `/* */`) — une docstring d'**une**
  ligne est permise ; le pourquoi va en ADR. Gate :
  `python ~/.claude/skills/julien-audit-comments/check_comments.py <fichiers touchés>`
- **Identifiants en anglais**, texte utilisateur en français.
- **Gates avant tout commit** : `python -m ruff check cooking_manager/ backend/ tests/` ·
  `python -m pyright` · `python -m pytest tests/`
- **Toute colonne ajoutée à un `CREATE TABLE` va AUSSI dans `MIGRATIONS_SQL`.**
- **Jamais de `localhost` depuis le poste** : `ssh srv759970 'curl -s localhost:8795/...'`.
- **Tests unitaires sans DB ni réseau.** Ce qui frappe l'API réelle est marqué `e2e`.
- **Pas d'hypothèse silencieuse** : une valeur non déductible est déclarée
  (`None` + motif), jamais devinée.
- ⚠️ **Rien ne se supprime avant la Task 8**, et la Task 8 ne commence pas sans le
  feu vert de la Task 2 puis une semaine d'observation réelle (Task 7).

## Le piège qui commande tout le plan

`food.key` est produit par `normalize_name()`. `nutrition.py` indexe par
`match_key()`, qui **retire en plus les particules**. Mesuré sur les 61 aliments en
base : **8 clés divergent**.

| `food.key` (stockage) | `match_key` (appariement) |
|---|---|
| `lait de coco` | `lait coco` |
| `pomme de terre cuite` | `pomme terre cuite` |
| `blanc de poulet cru` | `blanc poulet cru` |

Un lecteur DB qui indexerait par `food.key` perdrait ces 8 aliments — en
`unresolved`, sans erreur. **La clé de stockage reste `food.key` ; la clé
d'indexation en mémoire reste `match_key(food.name)`.** Vérifié : indexer par
`match_key` ne produit **aucune** collision sur les 61.

## Structure des fichiers

| Fichier | Responsabilité |
|---|---|
| `cooking_manager/food_repository.py` *(neuf)* | lignes DB → `dict[str, FoodEntry]`, pur, sans I/O |
| `backend/food_queries.py` *(neuf)* | les requêtes SQL qui alimentent le repository |
| `backend/food_regression.py` *(neuf)* | comparer vault et DB sur un menu réel |
| `cooking_manager/nutrition.py` *(modifié)* | `load_food_base*` retirées en Task 8 |
| `cooking_manager/purchase.py` *(modifié)* | convertit une pièce via `food_unit` |
| `backend/app.py` *(modifié)* | la source des macros devient la DB |
| `backend/cooking_mcp.py` *(modifié)* | outils `food_*` et `product_*` |
| `tests/test_food_repository.py`, `test_food_regression.py`, `test_purchase_units.py` *(neufs)* | un test par piège |

---

### Task 1: Le lecteur DB, qui rend le type existant

**Files:**
- Create: `cooking_manager/food_repository.py`
- Test: `tests/test_food_repository.py`

**Interfaces:**
- Consumes: `FoodEntry`, `Macros`, `match_key` (`cooking_manager/nutrition.py`).
- Produces: `base_from_rows(foods: list[dict], products: list[dict]) -> dict[str, FoodEntry]`.

- [ ] **Step 1: Write the failing test**

```python
from cooking_manager.food_repository import base_from_rows
from cooking_manager.nutrition import FoodEntry


def food(key, name, kcal=100.0, kind="generique", **kw):
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
        assert base["comte"].macros_for("comté")[0].kcal == 389.0

    def test_an_unlinked_product_never_shadows_a_food(self):
        """`a_rapprocher` veut dire « on ne sait pas » : il ne remplace rien."""
        base = base_from_rows(
            [food("comte", "Comté", kcal=417.0)],
            [{"name": "Comté Juraflore AOP", "food_key": None, "brand": "Juraflore",
              "macros_per_100g": {"form": "100g", "kcal": 389.0},
              "status": "a_rapprocher"}])
        assert base["comte"].macros_for("comté")[0].kcal == 417.0


class TestRefusal:
    def test_a_row_without_macros_is_absent_not_zeroed(self):
        base = base_from_rows([food("mystere", "Mystère", kcal=None)
                               | {"macros_per_100g": None}], [])
        assert "mystere" not in base

    def test_an_empty_base_is_empty(self):
        assert base_from_rows([], []) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_food_repository.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'cooking_manager.food_repository'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Lignes de la base → l'index d'appariement que nutrition.py consomme déjà."""

from __future__ import annotations

from .nutrition import FoodEntry, Macros, match_key

MACRO_FIELDS = ("kcal", "protein", "carbs", "fat")


def base_from_rows(foods: list[dict], products: list[dict]) -> dict[str, FoodEntry]:
    """`food` et `product` → index par clé d'appariement, préséance appliquée."""
    index: dict[str, FoodEntry] = {}

    for row in foods:
        entry = _entry(row.get("name") or row.get("key") or "", row, kind="generique",
                       storage_key=str(row.get("key") or ""))
        if entry is not None:
            _keep_best(index, entry)

    for row in products:
        food_key = row.get("food_key")
        if not food_key or row.get("status") != "linked":
            continue
        entry = _entry(row.get("name") or "", row, kind="marque",
                       storage_key=str(food_key))
        if entry is not None:
            _keep_best(index, entry, at=match_key(str(food_key)))

    return index


def _entry(title: str, row: dict, kind: str, storage_key: str) -> FoodEntry | None:
    macros = _macros(row.get("macros_per_100g"))
    if macros is None:
        return None
    return FoodEntry(key=storage_key, title=title, forms={"100g": macros},
                     source=str(row.get("source") or kind), kind=kind,
                     statut="", path="db")


def _macros(value) -> Macros | None:
    if not isinstance(value, dict):
        return None
    macros = Macros(**{f: _number(value.get(f)) for f in MACRO_FIELDS})
    if macros.kcal is None and macros.protein is None:
        return None
    return macros


def _number(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _keep_best(index: dict[str, FoodEntry], entry: FoodEntry,
               at: str | None = None) -> None:
    key = at if at is not None else match_key(entry.title)
    if not key:
        return
    current = index.get(key)
    if current is None or entry.rank < current.rank:
        index[key] = entry
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_food_repository.py -q`
Expected: PASS — 7 tests.

Si `test_the_index_key_drops_particles` échoue, c'est que l'index a été construit
sur `food.key` : `_keep_best` doit passer par `match_key(entry.title)`.

- [ ] **Step 5: Vérifier la couverture sur les 61 aliments réels**

```bash
ssh srv759970 'docker exec postgresql-shared psql -U cooking -d cooking_manager -t -A -F"|" -c "SELECT key, name FROM food ORDER BY key;"' > /tmp/food_keys.txt
```

```bash
python -c "
from cooking_manager.nutrition import match_key
rows = [l.split('|') for l in open('/tmp/food_keys.txt', encoding='utf-8') if '|' in l]
diff = [(k, match_key(n)) for k, n in rows if k != match_key(n)]
print(len(rows), 'aliments |', len(diff), 'dont la cle d appariement differe de la cle de stockage')
for k, m in diff: print('  ', k, '->', m)
"
```

Attendu : 61 aliments, 8 divergences — les mêmes que celles du tableau en tête de
plan. Un chiffre différent veut dire que la base a bougé : relire avant de continuer.

- [ ] **Step 6: Gates + commit**

```bash
python -m ruff check cooking_manager/ tests/
python -m pyright
python -m pytest tests/ -q
python ~/.claude/skills/julien-audit-comments/check_comments.py cooking_manager/food_repository.py
git add cooking_manager/food_repository.py tests/test_food_repository.py
git commit -m "feat(food): lire le referentiel depuis la base, sans changer le moteur

refs #69"
```

---

### Task 2: La non-régression, porte de la bascule

C'est l'étape qui protège. **Aucun consommateur ne change de source avant que ce
comparatif soit vert sur un menu réel.**

**Files:**
- Create: `backend/food_queries.py`
- Create: `backend/food_regression.py`
- Modify: `backend/app.py` — route `GET /api/food/regression`
- Test: `tests/test_food_regression.py`

**Interfaces:**
- Consumes: `base_from_rows` (Task 1), `load_food_base_cached`, `merge_sources`,
  `recipe_macros` (`cooking_manager/nutrition.py`).
- Produces: `fetch_food_rows(conn) -> tuple[list[dict], list[dict]]` (`food_queries`)
  et `compare_bases(vault, db, ingredients) -> dict` (`food_regression`) avec les clés
  `resolved_both`, `lost`, `gained`, `macro_gap`.

- [ ] **Step 1: Write the failing test**

```python
from backend.food_regression import compare_bases
from cooking_manager.nutrition import FoodEntry, Macros


def entry(title, kcal, kind="generique"):
    return FoodEntry(key=title, title=title, forms={"100g": Macros(kcal=kcal)},
                     source="test", kind=kind)


class TestComparison:
    def test_an_ingredient_lost_by_the_db_is_reported(self):
        """Le cas qui doit crier : le vault résolvait, la DB ne résout plus."""
        report = compare_bases({"lait coco": entry("lait coco", 230.0)}, {},
                               ["lait de coco"])
        assert report["lost"] == ["lait de coco"]
        assert report["resolved_both"] == 0

    def test_an_ingredient_gained_is_reported_not_hidden(self):
        report = compare_bases({}, {"lait coco": entry("lait coco", 230.0)},
                               ["lait de coco"])
        assert report["gained"] == ["lait de coco"]

    def test_a_macro_gap_is_reported(self):
        report = compare_bases({"comte": entry("comte", 417.0)},
                               {"comte": entry("comte", 389.0)}, ["comté"])
        assert report["macro_gap"][0]["ingredient"] == "comté"
        assert report["macro_gap"][0]["vault"] == 417.0
        assert report["macro_gap"][0]["db"] == 389.0

    def test_identical_bases_report_nothing(self):
        report = compare_bases({"comte": entry("comte", 417.0)},
                               {"comte": entry("comte", 417.0)}, ["comté"])
        assert report["lost"] == [] and report["gained"] == []
        assert report["macro_gap"] == [] and report["resolved_both"] == 1

    def test_an_ingredient_neither_base_knows_is_not_a_regression(self):
        report = compare_bases({}, {}, ["poudre de perlimpinpin"])
        assert report["lost"] == [] and report["gained"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_food_regression.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.food_regression'`

- [ ] **Step 3: Write `backend/food_queries.py`**

```python
"""Les requêtes qui alimentent le référentiel aliment."""

from __future__ import annotations

FOOD_SQL = """SELECT key, name, category, kind, ciqual_code, macros_per_100g,
                     conservation, source, verified_at
                FROM food"""

PRODUCT_SQL = """SELECT id, food_key, name, brand, ean, store, store_ref,
                        pack_count, pack_size_value, pack_size_unit, nutriscore,
                        macros_per_100g, last_price, price_per_kg, status, source
                   FROM product"""

UNIT_SQL = """SELECT food_key, unit, grams, source FROM food_unit"""


async def fetch_food_rows(conn) -> tuple[list[dict], list[dict]]:
    """Les deux jeux de lignes que `base_from_rows` consomme."""
    foods = [dict(r) for r in await conn.fetch(FOOD_SQL)]
    products = [dict(r) for r in await conn.fetch(PRODUCT_SQL)]
    return _decoded(foods), _decoded(products)


async def fetch_food_units(conn) -> dict[str, dict[str, float]]:
    """`food_key` → {unité: grammes}."""
    units: dict[str, dict[str, float]] = {}
    for row in await conn.fetch(UNIT_SQL):
        units.setdefault(row["food_key"], {})[row["unit"]] = float(row["grams"])
    return units


def _decoded(rows: list[dict]) -> list[dict]:
    import json

    for row in rows:
        value = row.get("macros_per_100g")
        if isinstance(value, str):
            row["macros_per_100g"] = json.loads(value)
    return rows
```

⚠️ `asyncpg` rend une colonne `JSONB` comme **chaîne** quand aucun codec n'est
posé : `_decoded` n'est pas une précaution décorative, sans elle `_macros` reçoit
un `str` et rend `None` — tous les aliments disparaissent en silence.

- [ ] **Step 4: Write `backend/food_regression.py`**

```python
"""Le vault et la base résolvent-ils les mêmes ingrédients, aux mêmes macros ?"""

from __future__ import annotations

from cooking_manager.nutrition import FoodEntry, match_entry

GAP_TOLERANCE = 0.5


def compare_bases(vault: dict[str, FoodEntry], db: dict[str, FoodEntry],
                  ingredients: list[str]) -> dict:
    """Deux index, une liste d'ingrédients réels → ce que la bascule changerait."""
    lost: list[str] = []
    gained: list[str] = []
    gap: list[dict] = []
    both = 0

    for name in ingredients:
        in_vault = match_entry(name, vault)
        in_db = match_entry(name, db)
        if in_vault and not in_db:
            lost.append(name)
            continue
        if in_db and not in_vault:
            gained.append(name)
            continue
        if not in_vault or not in_db:
            continue
        both += 1
        a, _ = in_vault.macros_for(name)
        b, _ = in_db.macros_for(name)
        if a is None or b is None or a.kcal is None or b.kcal is None:
            continue
        if abs(a.kcal - b.kcal) > GAP_TOLERANCE:
            gap.append({"ingredient": name, "vault": a.kcal, "db": b.kcal})

    return {"resolved_both": both, "lost": lost, "gained": gained,
            "macro_gap": gap, "checked": len(ingredients)}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_food_regression.py -q`
Expected: PASS — 5 tests.

- [ ] **Step 6: Ajouter la route**

Dans `backend/app.py`, à la suite de `GET /api/food/report` :

```python
@app.get("/api/food/regression")
async def food_regression(menu_slug: str):
    """Ce que la bascule vault → DB changerait sur un menu réel."""
    from cooking_manager import nutrition as nut
    from cooking_manager.food_repository import base_from_rows

    from .food_queries import fetch_food_rows
    from .food_regression import compare_bases

    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        names = [r["name"] for r in await conn.fetch(
            """SELECT DISTINCT ri.name
                 FROM menu m
                 JOIN menu_meal mm ON mm.menu_id = m.id
                 JOIN recipe_ingredient ri ON ri.recipe_id = mm.recipe_id
                WHERE m.slug = $1 AND ri.is_optional = FALSE""", menu_slug)]
        foods, products = await fetch_food_rows(conn)

    if not names:
        raise HTTPException(404, f"Menu sans ingrédients lisibles : {menu_slug}")

    vault = nut.load_food_base_cached(FOOD_BASE_ROOT)
    return {"menu": menu_slug} | compare_bases(vault, base_from_rows(foods, products), names)
```

La requête est vérifiée sur le VPS le 2026-09-07 : la table s'appelle
`recipe_ingredient` (pas `ingredient`) et `menu_meal` porte `recipe_id` (pas
`recipe_slug`). Sur `2026-09-07_semaine-aubagne-enfants` elle rend **63 ingrédients
distincts**.

⚠️ Une liste vide passerait pour « aucune régression » — c'est précisément le signal
absent que cette tâche existe pour empêcher. D'où le `checked` non nul au critère de
sortie : il vérifie qu'on a mesuré quelque chose, pas seulement que rien n'a crié.

- [ ] **Step 7: Déployer et mesurer sur les 4 menus réels**

```bash
ssh srv759970 'cd /opt/cooking-manager-2 && git pull && .venv/bin/pip install -q . && sudo systemctl restart cooking-manager'
for m in 2026-09-07_semaine-aubagne-enfants 2026-09-01_semaine-aubagne 2026-08-10_semaine-begles 2026-08-03_semaine-aubagne; do
  ssh srv759970 "curl -s 'localhost:8795/api/food/regression?menu_slug=$m' | python3 -c '
import sys, json
r = json.load(sys.stdin)
print(r[\"menu\"], \"| verifies:\", r[\"checked\"], \"| resolus des deux cotes:\", r[\"resolved_both\"])
print(\"   PERDUS:\", r[\"lost\"])
print(\"   gagnes:\", r[\"gained\"])
print(\"   ecarts:\", r[\"macro_gap\"])
'"
done
```

**Critère de sortie de la Task 2 — la porte de toute la phase 2 :**
- `lost` **vide** sur les quatre menus ;
- `macro_gap` **vide**, ou chaque écart expliqué par un produit `linked` qui prime
  légitimement sur son générique (à vérifier un par un, jamais en bloc) ;
- `checked` **non nul** — un zéro veut dire que la requête n'a rien lu, pas que
  tout va bien.

Un `lost` non vide **bloque** : corriger l'import ou le lecteur, pas le comparatif.

- [ ] **Step 8: Gates + commit**

```bash
python -m ruff check cooking_manager/ backend/ tests/
python -m pyright
python -m pytest tests/ -q
python ~/.claude/skills/julien-audit-comments/check_comments.py backend/food_queries.py backend/food_regression.py tests/test_food_regression.py
git add backend/food_queries.py backend/food_regression.py backend/app.py tests/test_food_regression.py
git commit -m "feat(food): la non-regression vault vs base, porte de la bascule

refs #69"
```

---

### Task 3: Basculer la source des macros

Ne commence **que** si la Task 2 est verte sur les quatre menus.

**Files:**
- Modify: `backend/app.py` — `recipe_macros_endpoint` et tout appel à `load_food_base_cached`
- Test: `tests/test_food_repository.py` (classe `TestSourceOrder`)

**Interfaces:**
- Consumes: `fetch_food_rows` (Task 2), `base_from_rows` (Task 1).
- Produces: aucune signature nouvelle — la source change, le contrat ne bouge pas.

- [ ] **Step 1: Write the failing test**

```python
class TestSourceOrder:
    def test_a_drive_product_sits_between_brand_and_generic(self):
        """Préséance du coach : marque (1) < drive (2) < générique (3)."""
        from cooking_manager.food_repository import base_from_rows
        from cooking_manager.nutrition import entry_from_product, merge_sources

        db = base_from_rows(
            [{"key": "comte", "name": "Comté", "kind": "generique", "source": "ciqual",
              "macros_per_100g": {"kcal": 417.0}}], [])
        drive = {"comte": entry_from_product("comté", {"kcal": "400"})}
        merged = merge_sources(db, drive)
        assert merged["comte"].kind == "generique"
        assert merged["comte"].macros_for("comté")[0].kcal == 417.0
```

⚠️ Ce test fige une vérité contre-intuitive : `merge_sources` garde le **rang le
plus petit**, et `generique` vaut 3 quand `drive` vaut 2 — donc le drive devrait
gagner. Lancer le test AVANT d'implémenter et **lire ce qu'il rend** : s'il échoue,
c'est l'assertion qu'il faut corriger, pas le moteur. La préséance existante est la
référence ; la bascule ne doit pas la changer.

- [ ] **Step 2: Run test to verify it fails (or passes for the wrong reason)**

Run: `python -m pytest tests/test_food_repository.py::TestSourceOrder -q`
Expected: FAIL — `ImportError` sur `base_from_rows` si la Task 1 n'est pas faite,
sinon un écart de préséance à trancher avec Julien avant de continuer.

- [ ] **Step 3: Basculer l'endpoint**

Dans `backend/app.py`, `recipe_macros_endpoint`, remplacer :

```python
    base = nut.merge_sources(nut.load_food_base_cached(FOOD_BASE_ROOT), drive)
```

par :

```python
    from cooking_manager.food_repository import base_from_rows

    from .food_queries import fetch_food_rows

    foods, products = await fetch_food_rows(conn)
    base = nut.merge_sources(base_from_rows(foods, products), drive)
```

`conn` est déjà ouvert dans cette fonction : ne pas prendre un second pool.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -q`
Expected: PASS — la suite entière, y compris `tests/test_nutrition.py` qui ne doit
pas bouger d'un test.

- [ ] **Step 5: Prouver sur une recette réelle, avant et après**

```bash
ssh srv759970 "curl -s 'localhost:8795/api/recipes/<slug>/macros' | python3 -m json.tool" > /tmp/macros_avant.json
ssh srv759970 'cd /opt/cooking-manager-2 && git pull && .venv/bin/pip install -q . && sudo systemctl restart cooking-manager'
ssh srv759970 "curl -s 'localhost:8795/api/recipes/<slug>/macros' | python3 -m json.tool" > /tmp/macros_apres.json
diff /tmp/macros_avant.json /tmp/macros_apres.json && echo "IDENTIQUE"
```

Prendre un `<slug>` d'un menu de la Task 2. Attendu : aucune différence, ou une
différence expliquée ligne à ligne. `coverage` et `conclusive` ne doivent pas
baisser.

- [ ] **Step 6: Gates + commit**

```bash
python -m ruff check cooking_manager/ backend/ tests/
python -m pyright
python -m pytest tests/ -q
git add backend/app.py tests/test_food_repository.py
git commit -m "feat(food): les macros se calculent depuis la base

refs #69"
```

---

### Task 4: `purchase.py` convertit une pièce

**Files:**
- Modify: `cooking_manager/purchase.py`
- Test: `tests/test_purchase_units.py`

**Interfaces:**
- Consumes: `fetch_food_units` (Task 2), `Need` et `Purchase` (`purchase.py`).
- Produces: `purchase_for(need, to_buy=None, unit_weights: dict[str, float] | None = None)`
  — paramètre **ajouté en dernier, avec un défaut** : tous les appels existants
  continuent de fonctionner.

- [ ] **Step 1: Write the failing test**

```python
from cooking_manager.pantry import Need
from cooking_manager.purchase import purchase_for


def need(name, qty, unit):
    return Need(name=name, name_normalized=name, qty=qty, unit=unit)


class TestConversion:
    def test_a_piece_becomes_grams_when_the_weight_is_known(self):
        p = purchase_for(need("oeuf", 6, "pièce"), unit_weights={"pièce": 60.0})
        assert p.grams == 360.0
        assert p.kind == "comptable"

    def test_without_a_weight_the_piece_stays_a_piece(self):
        """Pas d'hypothèse : un œuf ne pèse pas 100 g par défaut."""
        p = purchase_for(need("oeuf", 6, "pièce"))
        assert p.grams is None
        assert p.kind == "comptable"

    def test_a_measured_unit_is_untouched(self):
        p = purchase_for(need("farine", 500, "g"), unit_weights={"pièce": 60.0})
        assert p.kind == "mesure"

    def test_an_unknown_unit_stays_unresolved(self):
        p = purchase_for(need("truc", 2, "poignée"), unit_weights={"pièce": 60.0})
        assert p.kind == "non_resolu"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_purchase_units.py -q`
Expected: FAIL — `TypeError: purchase_for() got an unexpected keyword argument 'unit_weights'`

- [ ] **Step 3: Write minimal implementation**

Dans `cooking_manager/purchase.py`, ajouter le champ à `Purchase` puis le paramètre :

```python
    grams: float | None = None
```

```python
def purchase_for(need: Need, to_buy: float | None = None,
                 unit_weights: dict[str, float] | None = None) -> Purchase | None:
```

et, juste avant le `return` qui construit le `Purchase` comptable :

```python
    grams = None
    if unit_weights and need.unit in unit_weights and quantity is not None:
        grams = quantity * unit_weights[need.unit]
```

en passant `grams=grams` au `Purchase`. `quantity` est la quantité déjà arrondie
par la branche `comptable` — relire la fonction avant d'insérer, le nom local peut
différer.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_purchase_units.py tests/test_purchase.py -q`
Expected: PASS — 4 nouveaux tests, et les 13 de `test_purchase.py` **inchangés**.

- [ ] **Step 5: Câbler la source des poids dans la liste de courses**

Dans `backend/app.py`, la route `GET /api/menus/{slug}/shopping-list`, avant la
boucle qui appelle `purchase_for` :

```python
    from .food_queries import fetch_food_units

    weights = await fetch_food_units(conn)
```

puis, pour chaque besoin :

```python
        line["purchase"] = purchase_for(
            item, unit_weights=weights.get(item.name_normalized, {}))
```

⚠️ Ici — et **seulement** ici — les deux côtés parlent la même langue :
`fetch_food_units` est indexé par `food.key`, et `Need.name_normalized` sort du même
`normalize_name()`. Ne PAS passer par `match_key`, qui retirerait les particules d'un
seul côté et raterait les 8 aliments du tableau en tête de plan. La règle de la
Task 1 (indexer par `match_key`) vaut pour l'appariement d'un **ingrédient de
recette** ; elle ne vaut pas pour une clé de stockage confrontée à une autre clé de
stockage. Vérifier d'un `assert` avant de généraliser.

- [ ] **Step 6: Mesurer l'effet réel**

```bash
ssh srv759970 "curl -s 'localhost:8795/api/menus/2026-09-07_semaine-aubagne-enfants/shopping-list' | python3 -c '
import sys, json
r = json.load(sys.stdin)
lines = r.get(\"lines\", r.get(\"needs\", []))
with_g = [l for l in lines if (l.get(\"purchase\") or {}).get(\"grams\")]
print(len(lines), \"lignes |\", len(with_g), \"converties en grammes\")
for l in with_g[:10]: print(\"  \", l[\"name\"], \"->\", l[\"purchase\"][\"grams\"], \"g\")
'"
```

**Attendu : zéro ligne convertie.** `food_unit` contient **0 ligne** (vérifié en
base le 2026-09-07) : la seule unité lue dans tout le vault appartenait à un produit
resté `a_rapprocher`, donc sans `food_key` — elle est comptée dans
`units_without_food`, jamais écrite.

Ce n'est pas un échec du code, et il ne faut pas « réparer » ce zéro : c'est la
mesure de la phase 1 (les fiches ne portent pas d'unités d'usage). La Task 4 livre
**le chemin**, pas le résultat — le jour où une `food_unit` existe, la conversion
marche sans y retoucher.

⚠️ Ne pas valider cette tâche sur la sortie de l'API, qui ne montrera rien. Les 4
tests unitaires du Step 4 sont la preuve ; ce Step 6 ne fait que constater l'état de
la base. Ce que ce zéro chiffre vraiment, c'est ce que valent `ontology-manager#13`
et l'enrichissement des fiches.

- [ ] **Step 7: Gates + commit**

```bash
python -m ruff check cooking_manager/ backend/ tests/
python -m pyright
python -m pytest tests/ -q
git add cooking_manager/purchase.py backend/app.py tests/test_purchase_units.py
git commit -m "feat(purchase): convertir une piece en grammes quand le poids est connu

refs #80"
```

---

### Task 5: Les contraintes de personne quittent les fiches aliment

22 candidats sortent du rapport. « Léa : pas d'œufs durs » vit dans la fiche des
œufs, où **rien ne la lit** : seul `person.dislikes` est consulté par
`/compatibility`.

**Files:**
- Modify: `backend/app.py` — route `GET /api/food/person-constraints`
- Test: aucun test neuf — le filtre est déjà couvert par
  `tests/test_food_import.py::TestCollisions::test_a_dosage_line_is_not_a_person_constraint`

**Interfaces:**
- Consumes: `build_report` (phase 1, `backend/food_import.py`).
- Produces: rien de neuf en code. **Le livrable est une décision humaine par ligne.**

- [ ] **Step 1: Sortir la liste, lisible**

```bash
ssh srv759970 'curl -s "localhost:8795/api/food/report" | python3 -c "
import sys, json
for c in json.load(sys.stdin)[\"person_constraints\"]:
    print(c[\"sheet\"], \"|\", c[\"line\"])
"' > docs/conception/contraintes-personne-a-trier.txt
```

- [ ] **Step 2: Trier avec Julien, ligne par ligne**

Trois destinations, jamais une quatrième :

| Cas | Geste |
|---|---|
| Une aversion réelle (« Léa : pas d'œufs durs ») | `person.dislikes` |
| Un interdit (allergie, intolérance) | `person.forbidden` |
| Une note de dosage ou de contexte | **rien** — elle disparaît avec la fiche |

⚠️ Ne rien poser d'office. Une contrainte inventée s'affiche à l'utilisateur comme
une raison de refus : elle mentirait. En cas de doute sur une ligne, demander.

- [ ] **Step 3: Écrire les contraintes retenues**

Pour chaque ligne retenue, via l'API (jamais un `UPDATE` à la main : `dislikes` est
un tableau, un écrasement perd les valeurs existantes) :

```bash
ssh srv759970 'curl -s -X POST "localhost:8795/api/people/<id>/dislikes" \
  -H "Content-Type: application/json" -d "{\"add\": [\"oeuf dur\"]}"'
```

Si cette route n'existe pas encore, l'ajouter dans `backend/app.py` avec un
`array_append` idempotent plutôt qu'un remplacement — et un test qui prouve qu'un
second appel ne duplique pas.

⚠️ Écrire les termes **au singulier** (« oeuf dur », pas « oeufs durs ») : la
flexion va du singulier vers le pluriel, jamais l'inverse.

- [ ] **Step 4: Vérifier que le contrôle voit la contrainte**

```bash
ssh srv759970 'curl -s "localhost:8795/api/menus/2026-09-07_semaine-aubagne-enfants/compatibility" | python3 -m json.tool'
```

Attendu : un conflit apparaît là où la contrainte s'applique, avec sa raison. Si
rien ne bouge alors qu'un repas contient l'aliment, la contrainte n'est pas lue —
c'est un bug, pas une absence de conflit.

- [ ] **Step 5: Commit**

```bash
git add docs/conception/contraintes-personne-a-trier.txt backend/app.py
git commit -m "feat(person): les contraintes quittent les fiches aliment pour person.dislikes

refs #77"
```

---

### Task 6: Les outils MCP d'écriture

C'est ce qui rend le vault inutile à l'agent. Sans ces outils, le Coach Nutrition
de claude.ai n'a **aucun moyen** d'écrire, et il retournera aux fichiers.

**Files:**
- Modify: `backend/cooking_mcp.py`
- Modify: `backend/app.py` — les routes que le MCP appelle
- Test: `tests/test_food_api.py` *(neuf)*

**Interfaces:**
- Consumes: `_api` (helper existant de `cooking_mcp.py`), `fetch_food_rows` (Task 2).
- Produces: cinq outils MCP — `food_search(query)`, `food_detail(key)`,
  `food_upsert(key, name, macros, category=None, kind=None, ciqual_code=None)`,
  `product_upsert(name, brand=None, ean=None, store=None, store_ref=None, macros=None, food_key=None)`,
  `product_link(food_key, ean=None, store_ref=None)`.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestFoodApi:
    def test_search_finds_by_normalized_name(self, client: TestClient):
        r = client.get("/api/food/search", params={"q": "lait de coco"})
        assert r.status_code == 200
        assert any("coco" in f["key"] for f in r.json()["foods"])

    def test_detail_carries_units_and_products(self, client: TestClient):
        r = client.get("/api/food/pain complet")
        assert r.status_code == 200
        body = r.json()
        assert body["ciqual_code"] == "7110"
        assert "units" in body and "products" in body

    def test_link_writes_the_status(self, client: TestClient):
        r = client.post("/api/product/link",
                        json={"store_ref": "<un store_ref a_rapprocher>",
                              "food_key": "comte"})
        assert r.status_code == 200
        assert r.json()["status"] == "linked"

    def test_link_refuses_an_unknown_food(self, client: TestClient):
        r = client.post("/api/product/link",
                        json={"store_ref": "x", "food_key": "aliment inexistant"})
        assert r.status_code == 404
```

⚠️ Ces tests frappent l'API réelle et **écrivent en production** : ils sont marqués
`e2e` et ne tournent jamais par défaut (`pytest -m e2e`, opt-in).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_food_api.py -m e2e -q`
Expected: FAIL — 404 sur les routes, qui n'existent pas encore.

- [ ] **Step 3: Ajouter les routes**

Dans `backend/app.py` :

```python
@app.get("/api/food/search")
async def food_search(q: str, limit: int = 20):
    """Aliments dont le nom normalisé contient la requête."""
    from cooking_manager.ingredients import normalize_name

    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT key, name, category, kind, ciqual_code, macros_per_100g
                 FROM food WHERE key LIKE '%' || $1 || '%' ORDER BY key LIMIT $2""",
            normalize_name(q), limit)
    return {"query": q, "foods": [dict(r) for r in rows]}


@app.post("/api/product/link")
async def product_link(payload: dict):
    """Trancher un rapprochement produit → aliment."""
    food_key = (payload or {}).get("food_key")
    store_ref = (payload or {}).get("store_ref")
    ean = (payload or {}).get("ean")
    if not food_key or not (store_ref or ean):
        raise HTTPException(422, "food_key et (store_ref ou ean) sont requis")

    pool = await get_pool(DATABASE_DSN)
    async with pool.acquire() as conn:
        if not await conn.fetchval("SELECT 1 FROM food WHERE key = $1", food_key):
            raise HTTPException(404, f"Aliment inconnu : {food_key}")
        row = await conn.fetchrow(
            """UPDATE product SET food_key = $1, status = 'linked'
                WHERE ($2::text IS NOT NULL AND store_ref = $2)
                   OR ($3::text IS NOT NULL AND ean = $3)
             RETURNING id, name, food_key, status""",
            food_key, store_ref, ean)
    if row is None:
        raise HTTPException(404, "Produit introuvable")
    return dict(row)
```

`GET /api/food/{key}` (détail) suit le même patron : une ligne `food`, ses
`food_unit` et ses `product` rattachés, en trois requêtes dans la même connexion.

- [ ] **Step 4: Ajouter les outils MCP**

Dans `backend/cooking_mcp.py`, sur le modèle exact de `pantry_search` existant :

```python
@mcp.tool()
def food_search(query: str) -> dict:
    """Chercher un aliment du référentiel par son nom."""
    return _api("GET", "/api/food/search", params={"q": query})


@mcp.tool()
def product_link(food_key: str, store_ref: str = "", ean: str = "") -> dict:
    """Rattacher un produit acheté à un aliment du référentiel."""
    return _api("POST", "/api/product/link",
                json={"food_key": food_key, "store_ref": store_ref or None,
                      "ean": ean or None})
```

⚠️ Un intent MCP ajouté sans être câblé **échoue en silence**. Après déploiement,
appeler chaque outil une fois et lire la réponse.

- [ ] **Step 5: Déployer et vérifier les deux services**

```bash
ssh srv759970 'cd /opt/cooking-manager-2 && git pull && .venv/bin/pip install -q . && sudo systemctl restart cooking-manager cooking-mcp'
ssh srv759970 'curl -s "localhost:8795/api/food/search?q=lait%20de%20coco" | python3 -m json.tool'
ssh srv759970 'systemctl is-active cooking-mcp && journalctl -u cooking-mcp -n 20 --no-pager'
```

⚠️ `is-active` dit `active` même sur l'ancien code : lire le journal **et** appeler
un outil pour savoir ce qui tourne vraiment.

- [ ] **Step 6: Gates + commit**

```bash
python -m ruff check backend/ tests/
python -m pyright
python -m pytest tests/ -q
git add backend/app.py backend/cooking_mcp.py tests/test_food_api.py
git commit -m "feat(mcp): outils food_search, food_detail, product_link

refs #69, #82"
```

---

### Task 7: La base legacy, et la semaine d'observation

**Files:**
- Create: `docs/conception/legacy-logs-aliments.md`

**Interfaces:**
- Consumes: `GET /api/food/search`, `build_records` (phase 1).
- Produces: une décision écrite — résorbée, ou morte. **Pas « en cours ».**

- [ ] **Step 1: Mesurer le recouvrement**

`logs/aliments/` porte **73 fiches** (mesuré le 2026-09-07) et se dit en
« migration progressive » depuis juillet.

```bash
python -c "
from pathlib import Path
from cooking_manager.ingredients import normalize_name
legacy = Path(r'E:/Dr2/Dropbox/JULIEN/Obsidian/vault/Noyau/Coaches/Coach Nutrition/logs/aliments')
keys = {normalize_name(p.stem.replace('-', ' ')) for p in legacy.glob('*.md')}
import subprocess, json
out = subprocess.run(['ssh', 'srv759970',
  'docker exec postgresql-shared psql -U cooking -d cooking_manager -t -A -c \"SELECT key FROM food;\"'],
  capture_output=True, text=True).stdout
in_db = {l.strip() for l in out.splitlines() if l.strip()}
print(len(keys), 'fiches legacy |', len(keys & in_db), 'deja en base |', len(keys - in_db), 'absentes')
for k in sorted(keys - in_db)[:20]: print('   ABSENT', k)
"
```

- [ ] **Step 2: Trancher, et l'écrire**

Deux issues possibles, à arbitrer avec Julien sur le chiffre du Step 1 :

| Si | Alors |
|---|---|
| Les absentes sont des aliments réellement consommés | les importer via `food_upsert`, puis archiver le dossier |
| Ce sont des restes d'essais | déclarer la base morte et archiver, sans importer |

Écrire la décision dans `docs/conception/legacy-logs-aliments.md`, avec le chiffre
mesuré et la date. Une base « en cours de migration » sans date de fin est un
troisième écrivain silencieux.

- [ ] **Step 3: Observer une semaine réelle**

Avant toute suppression (Task 8), faire tourner **une semaine complète** sur la
nouvelle source : un menu écrit, des courses générées, des macros lues, des
déclarations de stock.

⚠️ **Cette étape ne s'accélère pas.** Elle existe parce qu'un rapport vert prouve
l'équivalence à un instant, pas sur un usage. Noter dans le diary chaque écart
constaté en cuisine.

- [ ] **Step 4: Commit**

```bash
git add docs/conception/legacy-logs-aliments.md
git commit -m "docs: la base legacy logs/aliments est tranchee

refs #69"
```

---

### Task 8: Retirer le code de lecture du vault

⚠️ **Ne commence pas avant** : Task 2 verte, Task 3 déployée, Task 7 Step 3 faite
(une semaine réelle observée). Un décommissionnement dont personne ne retire le
code laisse deux chemins d'écriture vivants — ADR 0010.

**Files:**
- Modify: `cooking_manager/nutrition.py` — retirer `load_food_base`,
  `load_food_base_cached`, `reset_food_cache`, `parse_food_sheet`, `_BASE_CACHE`
- Modify: `backend/app.py` — retirer `FOOD_BASE_ROOT` et la route
  `GET /api/food/regression`
- Modify: `tests/test_nutrition.py` — retirer les tests de lecture de fiches
- Modify: `CLAUDE.md` — la section « Référentiel aliment & produit »

**Interfaces:**
- Consumes: rien.
- Produces: rien. **Ce qui disparaît est le livrable.**

- [ ] **Step 1: Prouver que plus personne n'appelle**

```bash
python -c "
import subprocess
for name in ['load_food_base', 'load_food_base_cached', 'reset_food_cache',
             'parse_food_sheet', 'FOOD_BASE_ROOT']:
    out = subprocess.run(['git', 'grep', '-n', name, '--', 'backend', 'cooking_manager', 'web'],
                         capture_output=True, text=True).stdout
    print('===', name); print(out or '   aucun appel')
"
```

Chaque appel restant est soit à retirer, soit une raison de **ne pas** faire la
Task 8 maintenant. `backend/food_import.py` utilise `parse_food_sheet` : il part
avec, ou il est réécrit — l'import n'a plus de source à lire.

- [ ] **Step 2: Archiver les fiches**

```bash
ssh srv759970 'ls "/root/dropbox-mount/JULIEN/Obsidian/vault/Noyau/Coaches/Coach Nutrition/aliments-vérifiés" | head'
```

Vérifier le chemin réel du mount **avant** de déplacer quoi que ce soit. Puis, côté
poste, avec propagation vers le cloud (le VPS monte le cloud, pas le local) :

```bash
python -c "
import shutil, datetime
from pathlib import Path
root = Path(r'E:/Dr2/Dropbox/JULIEN/Obsidian/vault/Noyau/Coaches/Coach Nutrition/aliments-vérifiés')
dest = root / '_archive' / datetime.date.today().isoformat()
dest.mkdir(parents=True, exist_ok=True)
for sub in ('generiques', 'marques'):
    if (root / sub).is_dir():
        shutil.move(str(root / sub), str(dest / sub))
print('archive dans', dest)
"
rclone sync "E:/Dr2/Dropbox/JULIEN/Obsidian/vault/Noyau/Coaches/Coach Nutrition/aliments-vérifiés" \
  "dropbox:JULIEN/Obsidian/vault/Noyau/Coaches/Coach Nutrition/aliments-vérifiés" -v
```

⚠️ `rclone sync` **supprime à la destination** ce qui n'est plus à la source.
Vérifier la sortie ligne à ligne, et n'exécuter qu'après avoir listé les deux côtés.

- [ ] **Step 3: Retirer le code, et lancer la suite**

```bash
python -m pytest tests/ -q
```

Les tests qui échouent nomment ce qui lisait encore le vault. Les retirer aussi.

- [ ] **Step 4: Vérifier que l'API vit sans le vault**

```bash
ssh srv759970 'cd /opt/cooking-manager-2 && git pull && .venv/bin/pip install -q . && sudo systemctl restart cooking-manager && sleep 5'
ssh srv759970 "curl -s 'localhost:8795/api/recipes/<slug>/macros' | python3 -c '
import sys, json
r = json.load(sys.stdin)
print(\"coverage:\", r.get(\"coverage\"), \"| conclusive:\", r.get(\"conclusive\"))
print(\"non resolus:\", len(r.get(\"unresolved\", [])))
'"
```

Attendu : les mêmes chiffres qu'à la Task 3 Step 5. Une `coverage` qui chute dit
que le vault servait encore quelque chose.

- [ ] **Step 5: Mettre à jour le CLAUDE.md et committer**

Dans `CLAUDE.md`, la section « Référentiel aliment & produit » : remplacer les
règles de lecture du vault par les règles de lecture de la DB. **Écrire ce qu'on
fait, jamais ce qu'on s'interdit.**

```bash
python -m ruff check cooking_manager/ backend/ tests/
python -m pyright
python -m pytest tests/ -q
git add -A
git commit -m "refactor(food): retirer le code de lecture du vault aliments

Le referentiel vit en base. Fiches archivees dans aliments-verifies/_archive/.

closes #69"
```

---

## Hors périmètre de la phase 2, et déclaré comme tel

| Élément | Pourquoi pas maintenant |
|---|---|
| **Le rapprochement des 160 produits `a_rapprocher`** | c'est un choix **par produit**. `matching.py` livre les signaux ; la vérification par modèle et l'écran de validation sont un sous-projet à part entière |
| **L'axe `units` en ontologie** | `ontology-manager#13` — deux dépôts, et la phase 2 n'en dépend pas : `purchase.py` lit `food_unit`, pas l'ontologie |
| **Le frontmatter typé en YAML** | #85 — utile tant que le vault est lu, donc avant la Task 8 ; sans effet après |
| **Le ticket de magasin → catalogue Auchan** | dépend d'une session Auchan vivante. Un chemin qu'on ne peut pas éprouver ne s'écrit pas d'avance |
| **Le garde-manger (journal, niveaux, revue de rayon)** | sous-projet 2 de l'ADR 0010, à spécifier |

## Ce qui bloque quoi

```
Task 1 (lecteur)  ──► Task 2 (non-régression)  ──►  Task 3 (bascule)
                                │                        │
                                │                        ├──► Task 4 (purchase)
                                │                        ├──► Task 5 (contraintes)
                                │                        └──► Task 6 (MCP)
                                │                                  │
                                └──────────────────────────────────┴──► Task 7 (legacy + 1 semaine)
                                                                              │
                                                                              ▼
                                                                        Task 8 (retrait)
```

Les Tasks 4, 5 et 6 sont **indépendantes entre elles** : elles peuvent être prises
dans n'importe quel ordre, ou en parallèle, dès que la Task 3 est déployée.
