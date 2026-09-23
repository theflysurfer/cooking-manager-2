---
numero: 0034
titre: Le cap famille est pesco-méditerranéen, et les statuts de recette sont fermés
statut: accepté
date: 2026-09-23
concerne:
  - backend/db.py
  - backend/app.py
  - docs/decisions/0033-le-cadre-mediterraneen-entre-en-base.md
---

# 0034 — Le cap famille est pesco-méditerranéen, et les statuts de recette sont fermés

## Contexte

`Noyau/Cuisine/Intentions.md` portait depuis le 2026-05-12 le cap culinaire du foyer :
pesco-végétarien (le régime de Clémence fait référence) avec tendance méditerranéenne,
« alignement progressif, pas de rupture brutale ». Il portait aussi trois familles de recettes
à développer, deux vecteurs d'adhérence (le chocolat pour Léa et Clémence, le format brunch le
week-end), la modulation du blé actée le 2026-05-28 — et une convention de statuts de recette.

Deux choses le rendaient intenable. Le vault est déconnecté (ADR 0022) : ce cap ne pilotait
rien. Et sa convention de statuts (`piste`, `a-tester`, `validee`, `en-rotation`, `archivee`)
ne correspond à **aucune** valeur réellement écrite en base. Mesuré le 2026-09-23 sur
142 recettes : `to_test` 124, `active` 7, `draft` 5, `validated` 4, plus deux survivances
isolées — `valide` (`frittata-trois-fromages`) et `consommee`
(`ninja-creami-skyr-fromage-blanc-whey`, dont la fiche dit « préparée le 05/08, consommée le
06/08, retour goût/texture non encore renseigné »).

Rien n'empêchait d'écrire un statut de plus : la colonne `recipe.status` est un `TEXT` libre.

## Décision

Le cap du foyer est **pesco-méditerranéen** : le répertoire familial suit le régime de
Clémence et s'oriente vers le cadre méditerranéen de l'ADR 0033, sans rupture ni éviction. Le
blé reste au répertoire — pain blanc pour Léa, khorasan et focaccia pour Clémence, pain de
boulangerie pour Julien ; les bases sans blé sont une exploration, pas un remplacement.

Ce cap tient en trois axes déjà portés par la base et lisibles en SQL : `person.diet` pour les
régimes, `dietary_preference` pour ce qui pèse sans bloquer (ADR 0023), et la couverture
méditerranéenne dérivée de l'aliment (ADR 0033). Les familles de recettes à développer
deviennent des **issues GitHub**, pas des listes dans un fichier : elles se ferment.

`recipe.status` est **fermé** sur `draft`, `to_test`, `active`, `validated`. `valide` et
`consommee` sont migrés vers `validated`, et un `CHECK` refuse désormais toute autre valeur.

## Conséquences

- Écrire un statut hors des quatre valeurs fait échouer l'écriture au lieu de s'installer en
  silence. C'est un changement de contrat pour tout appelant de `POST`/`PUT /api/recipes` et
  pour l'import de livre.
- `ninja-creami-skyr-fromage-blanc-whey` passe `validated` alors que sa fiche dit le retour
  non renseigné et que `execution_count` vaut 0. Le statut enregistre qu'elle a été faite et
  mangée ; l'absence de `recipe_feedback` reste visible et se lit là, pas dans le statut.
- Les cinq nuances de la convention d'`Intentions.md` disparaissent : `en-rotation` et
  `archivee` n'ont pas de porteur dans les quatre valeurs. `active` couvre la rotation ; rien
  ne couvre « testée, non retenue » — c'est une lacune assumée, pas un oubli.
- Le cap n'a **aucun effet calculé** aujourd'hui : rien dans le code ne pondère une recette
  parce qu'elle est pesco. C'est un cadre de lecture pour la composition, comme le cadre
  méditerranéen l'est pour Julien.
- `Intentions.md` et `Inspirations.md` sont supprimés du vault : leur contenu vit désormais en
  issues, et un fichier qui reste à côté des issues diverge sans que rien ne le signale.

## Alternatives écartées

- **Migrer la convention d'`Intentions.md` vers la base** — elle décrit cinq états dont trois
  n'ont jamais été écrits. Migrer un vocabulaire que personne n'a employé, c'est graver une
  intention de mai dans une contrainte de septembre.
- **Laisser `recipe.status` libre** — c'est ce qui a produit `valide` et `consommee`, deux
  synonymes silencieux de `validated` qui faussent tout `GROUP BY status` et toute recherche
  par statut.
- **Passer `consommee` à `to_test`** — la fiche dit qu'elle a été préparée et mangée. La
  ranger en « à tester » effacerait un fait au profit d'une absence de retour.
- **Faire du cap une règle qui bloque** (refuser une recette carnée) — le foyer n'est pas
  pesco-végétarien à 100 % : Léa et Titouan n'ont pas de contrainte, et la viande rouge est
  tolérée 1 à 2 fois par semaine dans le cadre lui-même. Un blocage produirait des conflits
  que personne ne veut résoudre.
