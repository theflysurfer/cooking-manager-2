---
numero: 0038
titre: Le contenant entre dans le domaine, et dit quand il l'ignore
statut: accepté
date: 2026-09-25
concerne:
  - cooking_manager/packing.py
  - backend/app.py
issue: 155
supersede_partiellement: 0009
---

# 0038 — Le contenant entre dans le domaine, et dit quand il l'ignore

## Contexte

L'ADR 0009 §3 arrêtait le calcul à « un conditionnement » : *« il dit qu'il en faut un, jamais
lequel »*, au motif que le format vendu appartient à l'enseigne, pas au domaine.

La conséquence s'est mesurée le 2026-09-21 : **1150 g de poivrons demandés par 3 fiches,
0 sachet acheté**. Entre « il en faut » et « j'en prends 3 », personne ne faisait le *donc* — ni
le domaine, qui s'interdisait de connaître le format, ni le drive, qui ne connaît pas le besoin.

Or les données existaient déjà : `product` porte `pack_count`, `pack_size_value`,
`pack_size_unit`, `store`, `store_ref`, `last_price` (`backend/db.py:556-561`), et **aucun
consommateur** ne les lisait.

## Décision

**`cooking_manager/packing.py`**, sans I/O réseau comme tout le domaine. `pack_plan(purchase,
products)` rend un `PackPlan`.

Le format reste bien la propriété de l'enseigne — l'ADR 0009 avait raison sur ce point. Ce qui
change : le domaine ne s'interdit plus de **compter** avec un format qu'on lui fournit. Il ne
l'invente pas, il le reçoit.

**`pack_known: false` plutôt que `packs: 1`.** Un `1` inventé se lit comme un calcul. Le module
refuse de conclure et dit pourquoi dans cinq cas : aucun produit, aucun `pack_size_value`, une
taille nulle, une unité hors convertisseur, une unité de contenant incomparable à celle de
l'achat (400 g de sachet ne couvrent pas un besoin exprimé en pièces).

**Une dose ne se conditionne pas.** `purchase.kind == "dose"` rend `pack_known: false` avec son
motif : `purchase_for` a déjà tranché qu'une gousse d'ail n'est pas une quantité d'achat.

**Le plus petit contenant connu gagne.** Entre un sachet de 400 g et un de 2,5 kg pour 1150 g, le
petit fait moins de surplus. Un lot (`pack_count`) multiplie la taille avant comparaison.

**`surplus` se mesure en CONTENANTS, jamais en ratio** (décision 15 du grill du 2026-09-25) :
`surplus_packs = surplus / pack_size`. Un ratio ×2 classerait « 1 gousse d'ail → 1 tête » en
surplus, alors que `purchase_for` range déjà ça en `dose`.

## Alternatives rejetées

- **Laisser le drive faire le calcul** : il connaît le format, pas le besoin agrégé sur trois
  fiches. C'est précisément l'agrégation qui produit les 1150 g.
- **`packs: 1` par défaut quand le format est inconnu** : la panne que le CLAUDE.md nomme — une
  valeur qui vaut la même chose que la mesure ait réussi ou échoué.
- **Un seuil de surplus chiffré** : non tranché. « Un contenant de trop » est la règle ; un
  aliment sans `pack_size` connu ne peut de toute façon pas être jugé.

## Conséquences

- `GET /api/menus/{slug}/shopping-list` porte `pack_plan` sur chaque ligne, à côté de `purchase`.
  **`pack_known` se lit avant `packs`** : `null` dit « pas de format connu », jamais « un seul ».
- Le rattachement `recipe_ingredient.food_key → product.food_key` conditionne tout : une ligne
  non rattachée rend `pack_known: false`, ce qui est **exact** et non un échec silencieux.
- Un test ratchet (`TestRatchetContenantInconnu`) fixe l'invariant : un aliment sans `pack_size`
  ne rend jamais un nombre de paquets. Il couvre les cinq formes d'absence.
- **Supersède l'ADR 0009 §3.** Le reste de l'ADR 0009 (fusion des besoins, les quatre `kind`
  d'achat, l'arrondi vers le haut) reste en vigueur.
