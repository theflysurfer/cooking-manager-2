# ADR 0021 — Macros calculées depuis la table `food` en DB, pas le vault `.md`

**Date** : 2026-09-12
**Statut** : Accepté
**Supersède** : —

## Contexte

`/api/recipes/{slug}/macros` appelait `load_food_base_cached(FOOD_BASE_ROOT)`, qui parcourait
les 166 fichiers `.md` du vault `aliments-vérifiés/` (monté via rclone sur le VPS) à chaque
requête (avec cache mémoire). Ce chemin avait trois problèmes :

1. **Fragilité** — le mount rclone peut être en retard, absent, ou lent.
2. **Données fausses** — le parser frontmatter ligne à ligne transformait `null` YAML en chaîne
   `"null"` truthy (#85), corrompant `ciqual_code`, `nature`, etc.
3. **Redondance** — la table `food` contient les mêmes 166 entrées, importées par
   `POST /api/food/import`, avec les macros en JSONB déjà validé.

## Décision

`/macros` lit la table `food` via `_load_food_base_from_db()` (un seul `SELECT`).
Le vault `.md` ne sert plus qu'à l'import ponctuel (`/food/import`) et au diff (`/food/report`).

## Conséquences

- Le serveur de production ne dépend plus du mount rclone pour les macros.
- `load_food_base` et `load_food_base_cached` sont du code mort en production (à supprimer, #95).
- Le fix #85 (`_FM_ABSENT`) reste utile pour l'import, qui continue de lire les `.md`.
