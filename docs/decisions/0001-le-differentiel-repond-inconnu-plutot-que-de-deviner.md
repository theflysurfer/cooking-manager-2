---
numero: 0001
titre: Le différentiel répond « inconnu » plutôt que de deviner
statut: accepté
date: 2026-09-01
concerne:
  - cooking_manager/pantry.py
  - cooking_manager/ingredients.py
---

# 0001 — Le différentiel répond « inconnu » plutôt que de deviner

## Contexte

Le garde-manger n'est pas une liste de « basiques » : c'est un inventaire daté, avec des
quantités et des statuts. La question posée à chaque ingrédient n'est donc pas « est-ce un
produit courant qu'on a sûrement ? » mais « d'après l'inventaire, en ai-je assez ? ».

Deux situations empêchent d'y répondre avec certitude. L'appariement peut être douteux — le nom
écrit dans la recette ne recouvre pas exactement celui du stock. Et la comparaison de quantités
peut être impossible : « 3 filets » contre « 480 g » ne se convertit pas sans un poids unitaire
que personne n'a saisi.

Les deux erreurs possibles ne coûtent pas la même chose. Se tromper en disant « il t'en manque »
fait acheter un article de trop. Se tromper en disant « tu en as » fait **sauter un achat
nécessaire**, et cela ne se découvre qu'en cuisine, au moment de faire le plat.

## Décision

L'état `inconnu` est un citoyen de première classe du différentiel, au même rang que
`suffisant`, `insuffisant` et `absent`. Quand l'appariement ou la comparaison d'unités est
incertaine, l'app **demande** au lieu de trancher.

Le frais dont l'inventaire a plus de quatorze jours est réputé consommé, et cette déduction est
**énoncée** dans le champ `reason` — jamais appliquée en silence. Le sec échappe à la règle.

La normalisation des noms ne retire que ce qui ne change jamais l'identité d'un produit. « crème
fraîche » n'est pas « crème », « lait entier » n'est pas « lait demi-écrémé ». Sur-normaliser est
le mauvais côté de l'erreur.

## Conséquences

La liste de courses porte des lignes qui demandent une confirmation humaine, et elle en portera
toujours. C'est le prix accepté : une liste qui tranche seule est une liste qui fait rater un
dîner.

Le risque de dérive est l'inverse du risque initial — une liste trop bavarde cesse d'être lue, et
une liste qu'on ne lit plus ne protège de rien. D'où la contrepartie : un besoin sans quantité
chiffrée portant sur un article en stock répond `suffisant`, il ne pose pas de question sans
objet.

La règle d'ancienneté vide le frais d'un coup. Elle est donc paramétrable par `today` plutôt que
figée sur l'horloge : une règle qu'on ne peut pas figer dans un test est une règle qu'on ne peut
pas défendre.

## Alternatives écartées

**Convertir les unités au jugé** (un filet ≈ 120 g) : produit un chiffre faux qui a l'air juste,
et l'erreur se propage dans la somme sans laisser de trace.

**Raisonner par « basiques », comme Jow** : demande à l'utilisateur de retirer lui-même ce qu'il
possède, à partir d'une liste figée. L'app dispose d'un inventaire réel ; s'en priver reviendrait
à lui redemander ce qu'elle sait déjà.

**Répondre `absent` en cas de doute**, pour ne jamais rater un achat : noie la liste sous des
articles déjà en stock et ramène le problème d'origine — on rachète ce qu'on a.
