# 0003 — Trois axes de contrainte alimentaire, et des termes déclarés au singulier

- **Date** : 2026-09-03
- **Statut** : accepté
- **Contexte d'origine** : `docs/rapports/2026.09.03_14.17_97a20da_SESSION_pluriel-muet-exceptions-regime.md`, issues #53, #61
- **Complète** : [0002](0002-la-hierarchie-des-cuissons-vit-dans-le-vocabulaire.md)

## Contexte

`convives.py` ne savait qu'**ajouter** des interdits : `DIETS[diet]` pour le régime,
`forbidden` et `dislikes` pour la personne. Trois manques sont apparus le même jour,
et ils tiennent ensemble.

1. **Un régime était traité comme un absolu.** Clémence est pescétarienne *et* mange du
   boudin, les quenelles de veau et de volaille. Rien ne permettait de l'exprimer : le seul
   contournement aurait été de mentir sur son régime, donc de perdre tous les autres
   contrôles.
2. **`forbidden` servait de fourre-tout.** Les cuissons d'œufs refusées par Clémence et Léa
   y étaient rangées alors que ce sont des aversions. La distinction n'est pas cosmétique :
   elle change ce qu'on peut décider (une aversion se contourne au service, un interdit non).
3. **Le pluriel ne bloquait rien.** Découvert en écrivant un test qui utilisait « 200 g de
   lardons » comme exemple *bloquant* : le test a échoué, et c'était le code qui avait tort.

## Décision — trois axes distincts, jamais confondus

| Axe | Porte | Se contourne |
|---|---|---|
| `DIETS[diet]` | ce que le régime interdit | par une exception déclarée |
| `person.forbidden` | ce qui ne se discute pas | non |
| `person.dislikes` | aversion | au service |
| `person.diet_exceptions` | ce que le régime interdit mais que **cette** personne mange | — |

**Une exception dispense LA LIGNE qui porte l'expression, jamais le terme entier du
régime.** « Quenelle de veau » et « rôti de veau » partagent le terme bloquant `veau` :
lever le terme aurait laissé passer les deux. C'est `diet_waived_on(ligne)`, et non un
filtrage de `DIETS` en amont — la première version de la journée faisait cela, et a été
corrigée dans la même session.

Une exception ne touche jamais `forbidden` : un interdit personnel n'est pas une clause du
régime, et le lever par ricochet serait une faute.

## Décision — tout terme alimentaire se déclare au SINGULIER

`_contains_term()` compare en **mots entiers** — frontière volontaire, posée contre un faux
positif réel (« maïs » matchait dans « houmous **mais**on »). Mais les termes sont écrits au
singulier, si bien que la forme la plus courante d'une ligne d'ingrédient ne rencontrait
aucune entrée.

Mesuré avant correctif : **82 formes plurielles muettes** — `lardons`, `veaux`, `steaks`,
`saucissons`, `jambons`, `boeufs`. C'est la classe d'incident fondatrice du module (un menu
programmait du poulet pour une pescétarienne), rouverte sur le pluriel.

La flexion tolère « s » ou « x » final **sur chaque mot** de l'expression, et rien d'autre.
Deux passes ont été nécessaires : fléchir le dernier mot ne suffisait pas, « oeuf dur » doit
rencontrer « 2 œufs **durs** ».

⚠️ **La flexion va du singulier vers le pluriel, jamais l'inverse.** Un terme déclaré au
pluriel ne rencontre pas sa forme singulière — et cela ne produit **aucune erreur**, juste un
plat déclaré compatible. D'où la règle : régimes, `dislikes`, `forbidden` et
`diet_exceptions` se déclarent au singulier.

## Pourquoi ne pas lemmatiser

Une vraie lemmatisation (spaCy, lefff) traiterait « chevaux »/« cheval » et les accords
irréguliers. Rejetée : elle ajoute une dépendance lourde et un modèle à charger pour un
contrôle qui doit rester instantané, là où aucun terme carné du vocabulaire n'a de pluriel
irrégulier. Le jour où l'un en aura un, il sera plus honnête de l'écrire en toutes lettres
dans `DIETS` que de faire dépendre la sécurité alimentaire d'un modèle linguistique.

## Vérification

Les faux positifs historiques sont testés **dans les deux sens** — le pluriel doit bloquer,
et « maison », « julienne », « citronnelle » doivent rester hors d'atteinte de « maïs »,
« Julien », « citron ». Un correctif qui ne vérifierait que le sens « ça bloque enfin »
rouvrirait le défaut inverse, qui érode la confiance dans l'alerte tout aussi sûrement.

## Conséquence — `POST /api/seed` ne réécrit plus les préférences

Le seed réimposait `dislikes` et `forbidden` depuis ses constantes à chaque appel, alors que
le CLAUDE.md le présentait comme idempotent : les aversions saisies après coup auraient
disparu sans un mot. Ces listes sont désormais posées à la **création** seulement. Seuls
`role`, `diet` et `default_attendance` — qui sont structurels — restent mis à jour.
