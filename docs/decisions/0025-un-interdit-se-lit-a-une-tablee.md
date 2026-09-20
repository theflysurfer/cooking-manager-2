---
numero: 0025
titre: Un interdit se lit à une tablée, et une part se calcule
statut: accepté
date: 2026-09-21
concerne:
  - backend/app.py
  - cooking_manager/parts.py
  - cooking_manager/substitutions.py
  - cooking_manager/convives.py
---

# 0025 — Un interdit se lit à une tablée, et une part se calcule

## Contexte

Trois défauts de la même famille, trouvés en cherchant ce que Clémence mange quand il y a
de la viande.

1. `/api/recipes/{slug}/compatibility` testait les **14 lignes** de `person` : 42 « interdits »
   sur 37 recettes, dont 25 pour le poivre d'une personne qui ne mange pas là. Le paramètre
   `present_only` existait dans la signature et **n'était lu nulle part**.
2. `/api/menus/{slug}/compatibility` calculait ses conflits sur le **titre du plat** pendant
   que ses réparations lisaient les ingrédients. Un gratin contenant du riz blanc — interdit
   pour Julien — passait sans un mot, et deux conflits sur trois étaient invisibles.
3. Le moteur de substitution (47 règles, détection de contexte) ne réparait **rien** au niveau
   du menu ni des courses. La part pescétarienne se déclarait à la main dans une chaîne de
   caractères, `(part de Clémence)`, et la liste de courses ne l'achetait que par accident.

## Décision

Une compatibilité se demande **à une tablée**, résolue dans cet ordre : `?convives=` nommés →
`?day=&slot=` (présence réelle) → **les résidents** (`household_member.membership='resident'`).
Chaque conflit porte son `membership` : un `guest` est une contrainte d'invité, pas une règle
du foyer.

Les conflits du menu se calculent sur les **ingrédients**, comme ceux d'une recette.

Le moteur répare au niveau du menu ET des courses : une ligne conflictuelle est **découpée**
selon la part de la tablée concernée (1 personne sur 4 → 1/4 du substitut, 3/4 de l'original).
Une part déjà déclarée par le cuisinier prime, le moteur ne comble que les trous. Ce qui a été
réellement servi (`substitution_discovery`) prime sur la règle : un `success` écrase la
proposition, un `failure` la retire et la renvoie en `unrepaired`.

## Conséquences

- La réponse d'une recette dépend maintenant de qui mange : la même recette peut être compatible
  et incompatible le même jour. C'est la réalité, mais ça interdit de mettre en cache un verdict.
- La liste de courses achète un substitut que personne n'a validé. Le moteur propose `bœuf →
  lotte` dans un chili, ce qui n'a pas de sens culinaire ; seul un retour de table le corrigera.
- Un `regular_guest` est prévu par le schéma mais personne n'est classé ainsi : les invités se
  déclarent au coup par coup avec `?convives=`.
- La convention `(part de X)` dans un ingrédient survit et **prime** — deux mécanismes coexistent
  pour le même besoin, ce qui demande de savoir lequel a parlé (`declared_parts` le dit).

## Alternatives écartées

- **Garder les 14 personnes et étiqueter** — la réponse resterait illisible par défaut, et
  c'est le défaut qui est lu.
- **Refuser de répondre sans contexte (400)** — le plus honnête, écarté parce qu'il déplace la
  charge sur chaque appelant pour un gain nul : les résidents sont le contexte par défaut réel.
- **Remplacer l'ingrédient pour toute la tablée** — ce que faisait le moteur au niveau recette.
  Transforme le plat de tout le monde pour une seule personne.
- **Laisser la part en `## Notes` de la recette** — testé le 2026-09-20 : les notes ne sont ni
  parsées ni achetées, la part n'existait que dans le texte.
