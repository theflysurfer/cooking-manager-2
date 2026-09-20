---
numero: 0024
titre: La charge d'un plat se lit dans ses étapes, pas sur l'horloge
statut: accepté
date: 2026-09-21
concerne:
  - cooking_manager/effort.py
  - data/ontology/cooking-vocabulary.yaml
  - backend/app.py
---

# 0024 — La charge d'un plat se lit dans ses étapes, pas sur l'horloge

## Contexte

Reproche de Julien, 2026-09-20 : « un mafé un soir de semaine, ça ne le fait pas du tout ».
Le menu de la semaine portait trois dîners de ce calibre (50, 55 et 45 min).

Plafonner `total_time_min` classait les plats **à l'envers** : le mafé tient 50 min dont 35 de
mijotage où l'on ne fait rien, le risotto tient 35 min dont 18 collé à la casserole. Mesuré sur
les 104 recettes du corpus, les deux axes divergent sur 34 d'entre elles.

Le corpus lui-même n'avait aucun dîner de semaine : ses 37 recettes « rapides » sont des
assiettes froides de midi. Le compositeur ne proposait des plats du week-end que parce qu'il
n'avait que ça.

## Décision

L'ontologie `cooking-vocabulary` porte une facette `effort_bands` —
`hands_off` · `light_hands_on` · `hands_on` · `project` — en `probation`. Le **code** attribue
la bande en lisant les étapes (marqueurs d'attention continue, de façonnage), comme
`has_anchored_stew()` le fait déjà pour le mijoté.

Un plat tient un soir de semaine si sa bande n'est pas `project` **et** que l'horloge suit :
≤ 45 min en `hands_off`/`light_hands_on`, ≤ 20 min en `hands_on`. Sans étapes ou sans durée,
le verdict est `None` — jamais « facile ».

La bande n'est `active` que confirmée au service, dans `service_context`.

## Conséquences

- Une facette de plus impose de toucher **deux dépôts** : le générateur d'`ontology-manager` a
  un jeu de facettes codé en dur, un axe ajouté au seul YAML n'atteint pas l'artefact.
- Les seuils (45 min, 20 min) sont dans le code, pas dans l'ontologie : aucun champ numérique
  n'existe sur un concept. Les changer demande un commit, pas une édition de vocabulaire.
- Une recette sans étapes écrites devient invisible au filtre. C'est voulu : `absence_means`
  dit « PAS DÉRIVABLE », jamais « plat facile ».
- Le détecteur juge sur des marqueurs textuels : une étape qui décrit un geste exigeant sans
  le nommer passera à travers.

## Alternatives écartées

- **Plafonner l'horloge seule** — classe le mafé et le risotto à l'envers, mesuré.
- **Compter les étapes** — testé, puis retiré : 8 étapes triviales (`ninja-creami`, 10 min)
  donnaient `hands_on`. Le nombre d'étapes n'est pas un proxy d'attention.
- **Compter le repos comme de l'effort** — testé, puis retiré : `overnight-oats` (5 min, on
  mélange et on dort) sortait en `project`, avec 5 autres. Un repos long rend les mains libres.
- **Taguer les 104 recettes à la main** — 104 jugements posés à la place de Julien, et rien
  pour les recettes futures.
