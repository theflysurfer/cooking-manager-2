---
numero: 0005
titre: L'import de recette est une façade vers recipe-manager
statut: accepté
date: 2026-09-01
concerne:
  - backend/app.py
---

# 0005 — L'import de recette est une façade vers recipe-manager

## Contexte

Importer une page de livre demande un appel à un modèle multimodal. `recipe-manager` (port 8796)
possède déjà le modèle recette — il est propriétaire des tables `recipe`, `recipe_ingredient` et
`recipe_step` — ainsi que la clé d'API correspondante en credstore.

Cooking Manager 2 est colocataire de ces tables : il les lit et les écrit, mais ne les crée pas.

## Décision

CM2 ne parle pas au modèle. Son endpoint d'import **relaie** la requête vers `recipe-manager` et
retransmet le code de statut d'origine — un 409 « fiche déjà présente » arrive au front comme un
409, pas comme une panne serveur.

Le front n'a donc qu'une seule origine à appeler, et aucun CORS à ouvrir.

## Conséquences

Un import échoue si `recipe-manager` est arrêté. C'est assumé : la dépendance est déjà réelle
(CM2 dépend du service pour les photos), et `cooking-manager.service` la déclare en
`Requires=recipe-manager.service`.

La façade ajoute un saut réseau et une latence. Négligeable devant le temps d'appel au modèle.

Toute évolution du format d'import se fait dans `recipe-manager` ; CM2 n'a rien à redéployer tant
que le contrat HTTP ne change pas.

## Alternatives écartées

**Appeler le modèle depuis CM2** : dupliquerait le credential sur un second service et scinderait
la propriété du modèle recette entre deux dépôts. Deux endroits où corriger un prompt, deux clés
à faire tourner.

**Faire appeler `recipe-manager` directement par le front** : imposerait d'exposer ce service
publiquement et d'ouvrir le CORS, pour un gain nul côté utilisateur.
