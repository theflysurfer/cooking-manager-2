---
title: Référentiel aliment & produit — phase 2, état livré
axis: conception
proof_level: livre-mesure
upstream: [PLAN_referentiel-aliment-produit-phase1.md, SPEC_referentiel-aliment-produit.md]
downstream: []
status: livré — le plan d'exécution a été réécrit en description d'état le 2026-09-21
date: 2026-09-07
reecrit: 2026-09-21
issues: [69, 85, 90, 96, 101, 102, 118]
---

# Référentiel aliment & produit — phase 2, état livré

> Ce document était un **plan d'exécution** de 1180 lignes : huit tâches, leur code, leur
> ordre de blocage. Les huit sont faites — la dernière (retrait du code vault) l'a été le
> 2026-09-21 par #101. Réécrit en description d'état le même jour : un plan accompli qui
> détaille comment appeler `parse_food_sheet` est une consigne d'appeler du code supprimé.

## L'objectif de la phase 2, et son résultat

Faire basculer la source des macros du **vault markdown** vers la **base**, puis retirer le
code de lecture du vault — sans qu'aucune recette ne change de valeur au passage.

C'est fait, et la bascule finale a été mesurée : `/api/recipes/assiette-froide-crevettes-houmous/macros`
rend `1170,2 kcal · coverage 1.0` **avant et après** suppression de `food.macros_per_100g`.

## Où vivent les macros aujourd'hui

```
food        l'aliment, sans macros          (key, name, category, kind, ciqual_code, source)
food_form   UNE LIGNE PAR FORME             (food_key, label, kcal, protein, carbs, fat)
            201 lignes : 182 mono-forme + 19 formes de 8 aliments multi-formes
product     ce qu'on achète                 (food_key, nature single/composite, macros)
```

`_load_food_base_from_db()` joint `food` × `food_form` et construit un `FoodEntry` par aliment,
toutes formes comprises ; `macros_for()` choisit la forme d'après le nom de l'ingrédient
(« lentilles **cuites** » → 116 kcal, « lentilles » → forme crue par repli).

## Ce que la phase 2 a retiré

- `backend/food_import.py` (module entier), `build_records`, `write_records`, `build_report`
- `parse_food_sheet` et ses aides vault dans `nutrition.py`
- `FoodEntry.path` et `FoodEntry.statut`, qui n'avaient de sens que pour une fiche markdown
- `tests/test_food_import.py` et les tests de lecture de fiches de `test_nutrition.py`

Gardés, parce qu'ils servent au drive et non au vault : `read_energy` (et son plafond de
950 kcal, ratcheté) et `entry_from_product`.

## Ce que la phase 2 n'a pas fait

| Élément | État |
|---|---|
| Rapprochement des produits `a_rapprocher` | ouvert — `PATCH /api/product/{id}` (#102) permet de le faire un par un, aucun écran |
| Macros multi-formes d'un **produit** (bouillon sec/préparé) | ouvert, #112 — `food_form` référence `food`, pas `product` |
| Familles de protéine en ontologie | ouvert, #109 — `FAMILIES`/`SECONDARY` restent codées en dur |
| Identité de `pantry_item` | ouvert, #118 — ni `food_key` ni `product_id` |
| Alias d'aliment | ouvert, #117 — `viande hachee boeuf` n'est atteignable par aucune recette |

## Écriture, désormais

Il n'y a plus d'import : on écrit par l'API (#102).

```
GET/POST /api/food · GET/PUT/DELETE /api/food/{key}
GET/POST /api/food/{key}/form · DELETE /api/food/{key}/form/{label}
GET /api/product (?unlinked=true) · PATCH /api/product/{id}
```

Trois refus explicites plutôt qu'un silence : `status` hors vocabulaire → 422, `food_key`
inexistant → 404, rattachement d'un `composite` → 422 (ADR 0016).

## Où lire le pourquoi

ADR 0011 (les macros viennent de la base), 0016 (nature d'un produit), 0022 (le vault est
déconnecté). Les chiffres de couverture ne se recopient pas ici : ils se mesurent sur
`/api/recipes/{slug}/macros`, et `coverage`/`conclusive` priment toujours sur le total.
