---
title: Référentiel aliment & produit — phase 1, état livré
axis: conception
proof_level: livre-mesure
upstream: [SPEC_referentiel-aliment-produit.md]
downstream: [PLAN_referentiel-aliment-produit-phase2.md]
status: livré — le plan d'exécution a été réécrit en description d'état le 2026-09-21
date: 2026-09-07
reecrit: 2026-09-21
issues: [69, 80, 82, 84, 90]
---

# Référentiel aliment & produit — phase 1, état livré

> Ce document était un **plan d'exécution** de 1109 lignes : six tâches, leur code à écrire,
> leurs commandes à lancer. La phase est terminée, et depuis le 2026-09-21 le vault ne fournit
> plus aucune donnée aliment. Un plan accompli qui décrit du code supprimé se lit comme une
> consigne : il a donc été réécrit pour dire ce qui **est**, pas ce qu'il fallait faire.
> L'historique d'exécution vit dans les diaries de `docs/rapports/` et dans l'historique git.

## Ce que la phase 1 a livré

| Brique | Où elle vit | État |
|---|---|---|
| Séparation conditionnement / nom | `cooking_manager/packaging.py` — `split_packaging` | vivant |
| Unités d'usage d'un aliment | `cooking_manager/food_units.py`, table `food_unit` | vivant |
| Signaux de rapprochement | `cooking_manager/matching.py` — `compare(Signals, Signals)` | vivant, **enrichi** |
| Schéma `food` / `food_unit` / `product` | `backend/db.py` | vivant, **modifié** |
| Import des fiches vault | `backend/food_import.py` | **supprimé** (#101) |
| Rapport d'équivalence | `build_report` | **supprimé** avec lui |

## Ce qui a changé depuis, et qui invalidait ce plan

- **Le vault ne fournit plus aucune donnée aliment** (#101, 2026-09-21). `food_import.py`,
  `parse_food_sheet` et le dossier `aliments-vérifiés/` ne sont plus lus par aucun chemin de
  code. `import backend.food_import` lève `ModuleNotFoundError`. L'écriture passe désormais
  par l'API CRUD (#102).
- **`food.macros_per_100g` n'existe plus** (#97). Les macros vivent dans `food_form`, une
  ligne par forme — un aliment peut en porter plusieurs (`lentille` × `crues`/`cuites`).
- **Les invariants de la phase 1 ont quitté `food_import`** (#100). `link_food_key`,
  `clean_nature`, `product_natures` et `strip_brand` vivent dans `cooking_manager/matching.py`,
  et leurs ratchets dans `tests/test_matching.py` — sans vault ni fixture.

## Ce que la phase 1 n'a pas fait, et qui reste vrai

- Le rattachement produit → aliment reste **partiel** : `product.nature` distingue une lacune
  (`single`) d'une absence normale (`composite`), ADR 0016.
- `pantry_item` n'a toujours **aucune identité** : ni `food_key`, ni `product_id` (#118). C'est
  le problème que la phase 1 nommait en premier, et il est encore ouvert.

## Où lire le pourquoi

`docs/decisions/` — ADR 0016 (nature d'un produit), 0019 (la clé la plus spécifique gagne).
Les métriques ratchetées ne se recopient pas ici : elles vivent dans les tests, qui sont leur
seule vérité (`pytest -k "Ratchet or CompositeIsNever or ProductNature"`).
