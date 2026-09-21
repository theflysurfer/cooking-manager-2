---
numero: 0029
titre: Une occasion d'achat réutilise le vocabulaire de contexte
statut: accepté
date: 2026-09-21
concerne:
  - data/ontology/cooking-vocabulary.yaml
  - cooking_manager/bans.py
  - backend/db.py
---

# 0029 — Une occasion d'achat réutilise le vocabulaire de contexte

## Contexte

Julien, le 2026-09-21 : « pas de pompotes pour le quotidien, des pots de compote ». Puis, mis
devant une proposition d'interdit : « ce n'est pas une blacklist, c'est une habitude. Je pourrais
utiliser des pompotes pour certains cas, comme une envie particulière ou des pique-niques ».

Le refus n'est donc pas un refus : c'est un **défaut**. Or `shopping_preference` ne sait exprimer
que deux modalités — `blacklist`, qui bloque toujours, et `recurrent`, qui suggère sans jamais
bloquer. Aucune des deux ne dit « ceci vaut sauf occasion nommée ».

Le vocabulaire épinglé porte déjà un axe de contexte : `service_contexts` =
`batch_cooking, next_day, picnic, quick_meal, leftovers_base, guests, kids_only, brunch`. Son sujet
est aujourd'hui la recette (table `service_context`, alimentée par les retours de table). `picnic`
y figure déjà ; `everyday` n'existe pas, parce que le quotidien n'est pas un contexte de service
remarquable.

Fait annexe qui a fermé la voie de l'interdit : le catalogue Auchan ne nomme jamais un pot « pot »
(`AUCHAN Spécialité pomme sans sucres ajoutés 16x100g`), alors qu'il nomme la gourde
(`CHARLES & ALICE Gourdes compotes de pommes 12x90g`). Le conditionnement n'est discriminant que
dans un sens.

## Décision

L'occasion d'achat réutilise `service_contexts`, étendu d'une valeur `everyday`, plutôt que de
créer un axe jumeau. `shopping_preference` gagne une colonne `occasion` valant `everyday` par
défaut, lue au remplissage du panier : une préférence ne s'applique que dans son occasion, et une
gourde exige que l'occasion `picnic` soit nommée.

## Conséquences

- Un seul vocabulaire pour « dans quel contexte », avec deux consommateurs : la recette servie et
  l'achat. Toute valeur ajoutée profite aux deux.
- L'axe cesse d'être un vocabulaire mort : sans consommateur côté courses, `service_contexts`
  n'était lu que par les retours de table.
- **Le sujet de l'axe s'élargit** : `service_contexts` ne parle plus seulement du service. Le nom
  devient partiellement faux, et le renommer casserait la table `service_context` existante.
- L'ajout de `everyday` et de la colonne touche **deux dépôts** (ici et `ontology-manager`) plus un
  test : le générateur a un jeu de champs fixe, et un axe ajouté au seul YAML n'atteint pas
  l'artefact épinglé — le consommateur lit alors une valeur vide sans erreur.
- Tant que le remplissage du panier ne lit pas `occasion`, la colonne ne fait rien. La décision
  n'est donc acquise qu'une fois ce lecteur écrit.

## Alternatives écartées

- **Un axe `purchase_occasions` distinct** (`daily, picnic, craving, guests`) : plus juste
  sémantiquement — l'achat n'est pas le service — mais deux vocabulaires quasi jumeaux divergent,
  et `picnic` y serait défini deux fois.
- **La nuance en prose dans `reason`** : zéro code, mais rien n'en dérive. Un agent peut l'ignorer
  sans que rien ne le signale, ce qui est la définition d'une règle morte.
- **Porter l'occasion sur le repas** (`menu_meal`), les courses en dérivant : le plus puissant, les
  quantités et le conditionnement découleraient du menu. Écarté pour son coût — l'ingestion et le
  schéma des menus changent tous les deux.
- **Une `blacklist` sur `gourde`** : le mot est bien discriminant, mais l'interdit bloquerait aussi
  l'usage légitime occasionnel, que Julien a explicitement voulu préserver.
