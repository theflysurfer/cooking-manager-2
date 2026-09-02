# 0001 — Le moteur de substitutions est porté de la v1, pas réécrit

- **Date** : 2026-09-02
- **Statut** : accepté
- **Contexte d'origine** : `docs/rapports/2026.09.02_02.05_7aeffe3_SESSION_deep-review-handoff-lignes-receipt.md`, issues #53, #72, `theflysurfer/deep-research#49`

## Contexte

Le foyer compte une convive **pescétarienne**. `cooking_manager/convives.py` sait le détecter et
**écarter** un plat incompatible : `DIETS["pescetarian"] = MEAT + POULTRY`. Il ne sait rien en faire
d'autre — un plat de viande est refusé, point.

Tant que le répertoire de recettes est maison et déjà écrit pour le foyer, refuser suffit. Dès qu'on
ouvre sur les recettes du web (deep-research#49), la majorité des recettes trouvées contiennent de la
viande : refuser revient à annuler le volume qu'on vient de gagner.

`theflysurfer/cooking-manager` (v1) contenait déjà la réponse, jamais portée :
`server/src/services/intelligentSubstitutions.ts`, 42 règles qui remplacent poulet, bœuf, porc, veau,
agneau et charcuterie par le poisson adapté **au contexte** — cuisine, mode de cuisson, texture,
budget, priorité.

## Décision

**Porter les règles comme des données, sans les réinventer.** `cooking_manager/substitutions.py`
transcrit les 42 règles de la v1 une par une, avec leur `reason` d'origine. Le fichier v1 reste la
source : toute divergence se tranche en le relisant, jamais de mémoire.

Trois choix de structure :

1. **Le module reste du domaine pur.** Aucune I/O, aucune lecture de base. Il prend un nom de
   protéine et un `RecipeContext`, il rend une `Substitution` ou `None`. Qui décide s'il *faut*
   substituer — `person.diet` croisé avec les convives réellement à table — reste en dehors.
2. **Les règles sont indexées par régime** (`RULES_BY_DIET`), pas globales. Aujourd'hui seul
   `pescetarian` a une table ; un régime sans table rend `None` au lieu d'un remplacement inventé.
3. **Le motif remonte avec le résultat.** `Substitution` porte `reason`, `confidence` et la `rule`
   appliquée. Une substitution silencieuse est un plat dont plus personne ne sait pourquoi il a
   changé — c'est la panne que la session du 2026-09-02 a passé sa soirée à réparer.

## Ce qui a été corrigé au passage

Le portage a révélé un défaut de la v1 que rien ne signalait : **cinq valeurs de `cuisine` utilisées
par des règles n'avaient aucune liste de mots-clés** — `american`, `greek`, `pakistani`, `spanish`,
`vietnamese`. La détection de contexte ne pouvait donc jamais les émettre, et le bonus de ces règles
ne pouvait jamais s'appliquer. Les règles *paraissaient* contextuelles et ne l'étaient pas.

Les cinq tables manquantes ont été ajoutées, et un test vérifie désormais que **toute clé de contexte
citée par une règle existe dans les tables de détection**. C'est ce test qui a trouvé le défaut, à sa
première exécution.

## Ce qui est hérité et assumé tel quel

Sans aucun contexte détecté, le score se réduit à la priorité de base, et `poulet` rend **colin** —
la règle de panure, priorité 98, la plus haute du jeu. Ce n'est pas un bon choix pour un mijoté.

La cause est structurelle dans la v1 : la « criticité » d'une règle y est encodée dans sa priorité de
base, laquelle s'applique aussi quand il n'y a rien à départager. Les règles de repli sans
`cooking_methods` (bœuf → thon 60, porc → saumon 60, veau → bar 70) existent pour ce cas, mais
**`poulet` n'en a pas**.

Ce comportement est **épinglé par un test** (`test_sans_contexte_la_priorite_de_base_decide`) plutôt
que corrigé en silence. Le corriger changerait la sémantique héritée sur tout le jeu de règles ; ça
se décide, ça ne se glisse pas dans un portage. En pratique, un appel réel part d'une recette et
`detect_context` trouve presque toujours quelque chose.

## Conséquences

- Une recette de poulet au curry thaï devient une recette de **lotte** au curry thaï, avec le motif.
  La même en version poêlée donne du **thon** : c'est la cuisson qui tranche, pas le nom du plat.
- Le volume ouvert par deep-research#49 devient exploitable au lieu d'être filtré.
- Le branchement sur `person.diet` × `presence.py::attendees()` et l'affichage du motif restent à
  faire — refs #53.
