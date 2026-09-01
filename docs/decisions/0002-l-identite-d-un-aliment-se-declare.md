---
numero: 0002
titre: L'identité d'un aliment se déclare, elle ne se devine pas
statut: accepté
date: 2026-09-01
concerne:
  - cooking_manager/pantry.py
  - cooking_manager/ingredients.py
  - backend/db.py
  - backend/app.py
---

# 0002 — L'identité d'un aliment se déclare, elle ne se devine pas

## Contexte

`pantry_item` est alimenté par plusieurs voies : l'ingestion du vault, les tickets de caisse, la
saisie vocale, et bientôt le Coach Nutrition via le MCP. Sa clé d'unicité est
`(name_normalized, section)`, et `normalize_name()` ne retire délibérément pas les pluriels.

Ces deux voies écrivent donc le même aliment sous des clés différentes, et la base porte des
lignes qui se contredisent. Mesuré le 2026-09-01 : `oeufs` (vault, `out`) coexiste avec
`oeufs plein air x10` (ticket de caisse du 19/08, `ok`) ; de même pour `poivron rouge` /
`poivrons rouges` et `patate douce` / `patates douces`.

Le mécanisme qui devait empêcher cela existait pourtant. `_best()` départage plusieurs lignes du
même produit en faveur de la mieux dotée, « sinon un pot vide masquerait un pot plein rangé
ailleurs ». Mais `find()` retournait dès la première égalité exacte, sans jamais lui soumettre
les autres graphies. Une recette demandant « œufs » lisait `out` et remettait les œufs sur la
liste, alors qu'il y en avait dix.

## Décision

Une table `pantry_alias` déclare qu'une graphie désigne le même aliment qu'une ligne existante.
`find()` élargit son égalité exacte à tout le groupe d'alias, puis laisse `_best()` arbitrer.

Les alias sont **déclarés**, jamais inférés. Ils sont produits par une passe de dédoublonnage
supervisée, où un humain tranche chaque paire candidate.

`normalize_name()` n'est pas touchée.

## Conséquences

Un alias non déclaré ne corrige rien : le comportement reste celui d'aujourd'hui tant que
personne n'a arbitré. La correction est donc progressive et demande un entretien humain — c'est
assumé, c'est le prix d'un système qui n'invente pas d'équivalences.

L'alias pointe une ligne par sa clé étrangère plutôt que par son nom : une ligne supprimée
emporte ses alias, et un renommage ne casse rien.

La passe de dédoublonnage déclare des alias au lieu de fusionner les lignes. L'historique et la
provenance de chaque ligne survivent, mais la base garde des doublons visibles — moins propre à
l'œil, plus honnête sur d'où vient chaque observation.

## Alternatives écartées

**Relâcher `normalize_name()`** pour absorber les pluriels et les ligatures : corrigerait les
œufs, mais ferait aussi dire « tu en as de la sauce » parce qu'il y a de la sauce soja. C'est le
sens coûteux de l'erreur — un faux positif fait sauter un achat (cf. ADR 0001).

**Fusionner les lignes en double** lors du dédoublonnage : perd la provenance, donc la capacité
de savoir laquelle des deux observations était la plus fiable.

**Élire la ligne la plus récemment mise à jour** : `updated_at` date l'écriture, pas
l'observation. Après une ré-ingestion massive, toutes les lignes du vault portent la même
estampille du jour et gagneraient contre un ticket de caisse pourtant plus proche du réel.
