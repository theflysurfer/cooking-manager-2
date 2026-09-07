# 0005 — Les retours de table sont trois axes du vocabulaire, pas une note sur 5

## Contexte

`recipe_execution` portait déjà `rating` (1-5), `appreciated_by` (text[]) et `notes`.
Mesuré le 2026-09-07 : **4 lignes seulement**, toutes à 5/5, toutes « adoré par
tous », face à **49 repas** servis sur les 4 menus en base. Le mécanisme existait,
la matière non.

Deux limites du modèle, indépendantes du remplissage :

1. `appreciated_by` est une liste de noms — une personne y est ou n'y est pas.
   « Léa a adoré, Titouan a trouvé ça moyen » ne s'y écrit pas.
2. Une note unique fond deux jugements distincts. Un plat adoré de tous peut ne
   plus jamais revenir (trop long un soir de semaine) ; un plat moyen peut rester
   en rotation (dépannage rapide assumé).

## Décision

Trois axes, chacun répondant à une question différente, déclarés dans
`cooking-vocabulary` v0.4.0 (facettes `appreciations`, `replay_verdicts`,
`issue_kinds`) et **jamais** en constantes dans le code :

| Axe | Question | Portée |
|---|---|---|
| `appreciations` | à quel point **cette personne** a aimé | une ligne par convive (`recipe_feedback`) |
| `replay_verdicts` | que fait-on **du plat** ensuite | une ligne par plat servi (`recipe_verdict`) |
| `issue_kinds` | quelle est la **nature du défaut** | facultatif, explique un `adjust` |

Julien fournit du **texte libre** ; la conversion vers ces axes s'appuie sur les
`synonyms` du vocabulaire. D'où un test qui refuse toute valeur sans synonyme :
elle ne pourrait jamais être reconnue, et rien ne le signalerait.

Toutes les valeurs entrent en **`probation`** : quatre retours unanimes n'ont
encore rien trié.

## Bornage (`_scope` dans la source)

Ces axes ne s'appliquent **pas** aux repas hors domicile (« Restaurant Marseille »
au menu du 2026-09-01), aux restes (`<slot>_leftovers: true` — le jugement porte
sur le plat d'origine), ni aux remplissages macro sans préparation (« Fromage
blanc + whey »). Une absence de valeur y signifie **hors périmètre**, jamais
« personne n'a aimé ».

Sans ce bornage, un futur audit lirait ces trous comme des lacunes à combler, et
l'axe se remplirait de bruit ayant l'apparence de la donnée.

## Alternatives rejetées

- **Étendre `appreciated_by` en JSONB {nom: note}** — porterait la nuance, mais
  garderait la fusion des deux jugements (aimé ≠ à refaire) et resterait un
  vocabulaire implicite, invérifiable par un test.
- **Un axe unique « à refaire / à oublier »** — perd l'information par personne,
  qui est précisément ce qui oriente les menus d'une tablée à contraintes multiples.

## Conséquences

- Le générateur d'ontologie a un jeu de facettes **fixe** : les trois facettes ont
  dû être propagées dans `ontology_manager/cooking.py` (autre dépôt) pour atteindre
  l'artefact. Un test le vérifie — sans lui, une facette perdue se lirait comme un
  vocabulaire vide, sans erreur.
- `recipe_feedback` et `recipe_verdict` existent en schéma ; **aucune route ne les
  écrit encore**. La conversion du texte libre reste à câbler.
- `recipe_execution` n'est pas supprimée : ses 4 lignes sont la seule trace
  existante, à reprendre lors de la revue rétrospective.
