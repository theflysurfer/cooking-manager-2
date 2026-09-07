# 0007 — Un terme de régime ambigu exige un contexte, il ne se compare pas en mot nu

- **Statut** : accepté
- **Date** : 2026-09-07
- **Supersède** : rien. Corrige un angle mort de l'ADR 0003 (flexion des termes).

## Contexte

Le contrôle de compatibilité du menu du 7 au 14 septembre a rendu deux conflits.
Le second portait sur un plat sans la moindre trace animale :

```
lundi dinner  Poêlée de légumes verts, pois chiches rôtis et comté
    Clémence | régime pescetarian | roti
```

`MEAT` contient `roti` — la pièce de viande. Le repli retire les accents, la
tolérance de flexion de l'ADR 0003 accepte la marque du pluriel, et « rôtis »,
participe passé d'une cuisson, devient un rôti de bœuf.

Le mécanisme incriminé est exactement celui que l'ADR 0003 a voulu : mots
entiers, singulier vers pluriel. Le défaut n'est pas dans la comparaison, il est
dans **le terme** : `roti` est à la fois un nom de viande et le participe passé
le plus courant de la cuisine française. La même ambiguïté guette `magret` non,
mais `blanc` (blanc de poulet / blanc d'œuf / blanc de poireau), `filet` et
`cuisse` la portent.

Un conflit faux coûte plus cher qu'un conflit manqué : il apprend à ignorer les
alertes, puis à les désactiver. C'est écrit en tête de `tests/test_convives.py`
depuis l'origine, et c'est précisément ce qui a failli arriver.

## Décision

Un petit ensemble de termes — `CONTEXT_REQUIRED` — est comparé par un **motif
explicite** au lieu du gabarit « mot entier fléchi ». Le motif exige un contexte
nominal : un article devant (`un rôti`, `le rôti`) ou un complément de matière
derrière (`rôti de porc`, `rôti d'agneau`).

Ce qui a été volontairement écarté du motif : `rôti au four`, `rôti aux herbes`.
Ce sont des compléments de **cuisson**, pas de matière — et ce qu'ils
accompagnent (« poulet rôti au four ») est déjà nommé ailleurs dans `POULTRY`.
Le durcissement ne perd donc aucune détection réelle.

## Conséquences

- Un plat végétal cuit au four ne déclenche plus de conflit de régime.
- `_term_pattern` consulte `CONTEXT_REQUIRED` avant de construire son gabarit :
  un terme y figurant n'est plus jamais comparé en mot nu.
- **Le prix** : ajouter un terme ambigu à `MEAT` ne suffit plus, il faut écrire
  son motif. Un terme ambigu oublié reste muet dans les deux sens.
- Deux tests bornent le comportement, un par direction : les pois chiches rôtis,
  les légumes rôtis et les tomates rôties ne bloquent pas ; le rôti de porc,
  d'agneau, de veau et « un rôti du dimanche » bloquent toujours.

## Défaut voisin corrigé dans la foulée

`check_meal` repliait le texte du plat et les termes de **régime**, mais passait
`forbidden` et `dislikes` **sans les replier**. Tout interdit ou aversion écrit
avec un accent était donc muet : « épinards cuits » (Léa), « céleri »
(Clémence), « gésier ». Même famille que le pluriel muet du 2026-09-03 — une
comparaison qui échoue en silence et rend un plat compatible.
