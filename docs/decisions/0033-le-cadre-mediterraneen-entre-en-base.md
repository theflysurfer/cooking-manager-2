---
numero: 0033
titre: Le cadre méditerranéen entre en base et se dérive de l'aliment
statut: accepté
date: 2026-09-23
concerne:
  - data/ontology/cooking-vocabulary.yaml
  - cooking_manager/cooking-vocabulary.json
  - cooking_manager/mediterranean.py
  - cooking_manager/food_repository.py
  - cooking_manager/matching.py
  - backend/app.py
  - backend/db.py
---

# 0033 — Le cadre méditerranéen entre en base et se dérive de l'aliment

## Contexte

Le cadre méditerranéen de Julien vit depuis le 2026-05-22 dans une note du Coach Nutrition,
`Noyau/Cuisine/Cadre-mediterraneen.md` : profil en sèche, 9 critères à cocher, cibles macros
d'une journée type. Le vault est déconnecté depuis l'ADR 0022 — rien de ce qu'il porte
n'atteint l'application. Le cadre est donc une lecture humaine, et rien d'autre.

Ce qui existait côté base au moment de la décision, mesuré les 22 et 23/09/2026 :

- `recipe.mediterranean_criteria` (`INTEGER[]`) porte des annotations **manuelles** sur
  **3 recettes sur 142** (`{2,4}`, `{2,4}`, `{3,6,8}`), **zéro occurrence** dans `web/`. Rien
  ne les produit, rien ne les lit.
- `food.category` **ne sépare pas** légumineuse et féculent : ses 34 lignes
  `feculents-legumineuses` rendent le critère 3 indérivable.
- `hareng fume doux` est classé `poisson` tout court, alors que le critère 5 vise les
  poissons **gras**.
- `food.kind` est vide sur **177 aliments sur 192** ; les 12 valeurs présentes ne viennent
  d'aucun vocabulaire — elles ont été écrites au fil de l'eau.
- Le rattachement aliment ↔ recette vaut **0 ligne sur 1169** (`recipe_ingredient.food_key`).

Les cibles macros posent un second problème. La note du 22/05 annonce 1 800–1 900 kcal et
180–200 g de protéines. La grille `Coaches/Coach Nutrition/_coach.md` v2.10.33, révisée le
2026-07-17 et qui se déclare « source de vérité unique », annonce des planchers plus bas :
1 700 kcal et 160 g de protéines.

## Décision

Les 9 critères deviennent une facette `mediterranean_criteria` de `cooking-vocabulary`, et
`food.kind` devient la facette fermée `food_kinds`. Chaque critère déclare, par
`satisfied_by`, les `food.kind` qui le satisfont : **la couverture se dérive de l'aliment,
jamais d'une saisie à la main**. Le critère 9 (eau + thé vert) ne déclare aucun `food.kind` —
aucun ingrédient de recette ne le porte — et se lit **hors de portée**, jamais « non tenu ».

`GET /api/menus/{slug}/mediterranean` rend cette couverture. Elle annonce `measured: false`
**avant toute liste** tant qu'aucun ingrédient n'est rattaché à un aliment, comme
`slots_uncomposed`, `preferences_unmeasurable` et `conflicts_uncovered`.

Les cibles macros entrent en base dans `nutrition_target` — **une seule ligne**, pas de
colonne `day_kind` —, avec `source` et `since` qui disent d'où elles viennent et depuis
quand. Elles portent **les chiffres de la note du 22/05** : 1 800–1 900 kcal, 180–200 g de
protéines. Julien a maintenu ces chiffres après avoir été mis deux fois devant la révision du
17/07 ; c'est sa décision, prise en connaissance de cette révision.

`GET /api/menus/{slug}/nutrition` confronte le menu à cette cible. Il rend `target_age_days`
**sans seuil de péremption** — l'âge se lit, il ne se juge pas — et **ne conclut pas** tant
qu'un ingrédient du jour n'est pas compté : `verdict: null` et les manques nommés.

## Conséquences

- Les deux routes rendent aujourd'hui `measured: false` et `verdict: null` sur tout le corpus :
  0 ligne rattachée sur 1169. **C'est le comportement voulu** — un zéro dérivé d'une source
  vide n'est pas une mesure. Elles ne diront quelque chose qu'une fois le rattachement fait
  (PLAN phase 3 étape 3).
- Une valeur ajoutée au seul YAML n'atteint pas l'artefact : le générateur a un jeu de champs
  fixe. Ajouter un critère ou un `food.kind` coûte **deux dépôts plus un test**
  (`2026.07 Ontology Manager` et ici).
- `food.kind` devient refusable : `POST`/`PUT /api/food` rend 422 sur une valeur hors
  vocabulaire. Les 12 valeurs déjà en base sont reprises dans la facette — **renommées en
  anglais dans la même migration** (`beurre` → `butter`, `poisson` → `fish`…), parce qu'un
  identifiant s'écrit en anglais et qu'un axe mi-français mi-anglais se serait figé tel quel.
  Le renommage et la facette partent ensemble : séparés, `satisfied_by` citerait des clés
  qu'aucun aliment ne porte et la couverture lirait zéro partout sans rien dire.
- `food.kind` alimentait `FoodEntry.kind`, qui classe une **provenance** (`marque`, `drive`,
  `generique`) et pas une famille culinaire : les 15 aliments qualifiés sortaient du barème.
  `base_from_form_rows` pose désormais `generique` et indexe sur la clé d'appariement, comme
  `base_from_rows` le faisait déjà — « lait de coco » ne s'appariait à rien.
- Les 8 `food.kind` que le cadre exige et que la base ne porte pas encore
  (`legume`, `fruit`, `cereale-complete`, `cereale-raffinee`, `poisson-gras`, `poisson-maigre`,
  `huile-olive`, `huile-autre`) entrent en `probation` : ils viennent d'une note de cadrage,
  pas d'un usage mesuré.
- Les 3 annotations manuelles de `recipe.mediterranean_criteria` restent en base et ne sont
  pas lues par la dérivation. Rien ne les rapproche : elles témoignent d'un geste abandonné.
- `Cadre-mediterraneen.md` **reste dans le vault**. C'est la seule lecture humaine du cadre
  tant que la dérivation ne mesure rien, et il porte davantage que les 9 critères (menus types,
  cuissons, rôle de la whey).

## Alternatives écartées

- **Dériver la couverture de `food.category`** — elle ne sépare ni légumineuse et féculent
  (critère 3), ni poisson gras et maigre (critère 5). Deux critères sur huit seraient muets
  sans rien dire.
- **Saisir `mediterranean_criteria` à la main sur chaque fiche** — c'est ce qui existait :
  3 recettes annotées sur 142 en quatre mois, et aucune relecture possible quand un ingrédient
  change.
- **Retenir les planchers de la grille v2.10.33 (1 700 kcal / 160 g)** — plus récents, mais
  Julien a maintenu la note du 22/05 après en avoir été informé deux fois. La base enregistre
  sa décision, pas la source la plus fraîche. La révision est nommée ici pour qu'on sache que
  l'écart est su.
- **Une colonne `day_kind` dans `nutrition_target`** (journée standard / cross / muscu lourde /
  refeed) — la source retenue ne décrit **qu'une** journée type. Poser quatre colonnes pour
  trois valeurs qu'on n'a pas, c'est fabriquer trois lignes vides qui se liraient comme des
  cibles.
- **Compter le critère 9 (eau + thé) comme non tenu** — aucun ingrédient de recette ne porte
  l'eau bue dans la journée. Un critère qu'on ne peut pas mesurer et qu'on affiche à zéro fait
  baisser un score sans qu'aucun geste ne puisse le relever.
