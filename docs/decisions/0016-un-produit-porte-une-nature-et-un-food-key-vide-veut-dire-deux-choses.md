# 0016 — Un produit porte une nature, et un `food_key` vide veut dire deux choses

- **Date** : 2026-09-08
- **Statut** : accepté
- **Issue** : #90 · lié #69, #88, #82

## Contexte

`GET /api/food/report` annonçait **160 produits « non rattachés » sur 170**, tandis
que `missing`, `macro_mismatch` et `collisions` étaient à zéro. Les trois gates de
l'ADR 0011 ne regardent pas là où le trou est.

Le rapprochement automatique de ces 160 vers les 61 clés de `food`, par
`normalize_name`, a été mesuré :

```
exact       0
inclusion  11   dont 6 faux
sans piste 149
```

Aucune correspondance exacte, et les inclusions majoritairement fausses :
« Picard Lasagnes Légumes Grillés Mozzarella » → `mozzarella`, « Picard Salade
Lentilles Saumon Fumé Pomme » → `saumon fume`, « onigiri-guacamole-avocat » →
`avocat`.

## Décision

`product` porte une colonne **`nature`**, dont les valeurs viennent de la facette
`product_natures` du vocabulaire culinaire (jamais d'une table écrite dans le
code) :

| Valeur | Sens | Ce qu'un `food_key` vide veut dire |
|---|---|---|
| `single` | le produit est UN aliment conditionné ; ses macros sont celles de l'aliment, à la marque près | **lacune du référentiel** — l'aliment devrait exister |
| `composite` | plusieurs ingrédients ; les macros lui sont propres | **normal** — il n'a pas d'aliment parent |

L'axe a été **appliqué à la main aux 170 produits avant d'être posé**, comme
l'exige l'étape de bornage : **90 `single`, 80 `composite`, zéro qui résiste**.

## Ce que ça change

- Le compteur passe de **160 à 83**. Les 77 autres sont des composites : créer
  leurs « aliments parents » aurait rempli le référentiel de plats.
- Trois composites étaient **déjà mal rattachés** en base et sont détachés :
  `aubergines-provencales` → `aubergine`, `courgettes-cuisinees-provencale` →
  `courgette`. Les macros d'une aubergine à la provençale ne sont pas celles
  d'une aubergine.
- `unclassified_products` est exposé **à part** : une nature absente est
  *PAS INSTRUIT*, jamais une lacune. Elle ne se comble pas par défaut.

## Pourquoi pas un meilleur matcher

Parce que le défaut n'est pas dans le rapprochement mais dans ce qu'il cherche.
Un plat rattaché à un ingrédient rend un `food_key` non nul : il **sort du compte
des non-rattachés et se lit comme réparé**, en donnant les macros d'un ingrédient
au plat entier. Sans l'axe, tout matcher est faux par construction — et
silencieusement.

## Tensions assumées

Déclarées dans `known_tensions` de la source, pas ici :

1. Un mélange nature (« Fruits Rouges surgelés », « Trio de Poivrons ») porte
   plusieurs aliments sans transformation. Classé `single` parce que le
   référentiel porte déjà des aliments-mélanges — c'est un choix, pas une
   évidence.
2. `food` contient déjà des préparations promues au rang d'aliment
   (`soupe pois casse industrielle`, `vinaigrette classique`, `flan patissier`).
   La frontière traverse donc aussi le référentiel aliment, où rien ne la déclare.
3. Un assaisonnement composé (pesto, pâte de curry) est `composite` par
   construction alors qu'on ne le mange pas comme un plat. La valeur dit « pas
   d'aliment parent », pas « c'est un plat ».

## Conséquence sur le moteur d'ontologie

Le bornage `_scope` vivait dans la source depuis la v0.5.0 et **n'était porté par
aucun artefact** : le consommateur lisait un bornage vide, sans erreur. Il est
désormais rendu, indexé par facette — un `_scope` racine anonyme n'aurait de toute
façon pas pu en accueillir un second sans écraser le premier en silence.

## Ce qui reste ouvert

La nature vit en base, pas encore dans les fiches `marques/*.md`. Le rapport la
lit des deux côtés, le vault primant lorsqu'il la déclare. Écrire `nature:` dans
les fiches reste à faire — #90.
