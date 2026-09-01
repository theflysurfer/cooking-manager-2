---
numero: 0004
titre: Un repas non relié vaut mieux qu'un repas mal relié
statut: accepté
date: 2026-09-01
concerne:
  - backend/ingest.py
---

# 0004 — Un repas non relié vaut mieux qu'un repas mal relié

## Contexte

Chaque créneau d'un menu porte un intitulé rédigé à la main — « Gratin
courgettes-ricotta-feta + crevettes sautées citron ». Le titre de la fiche recette correspondante
est écrit à un autre moment, et diverge presque toujours d'un mot ou deux. L'appariement par
titre échoue donc structurellement.

Une erreur de liaison ne se voit pas au moment où elle est faite : elle se voit en cuisine, quand
les ingrédients achetés ne sont pas ceux du plat prévu.

## Décision

Deux marqueurs explicites dans le frontmatter priment sur toute heuristique. `<slot>_slug`
désigne la fiche et court-circuite la recherche. `<slot>_leftovers` déclare un repas de restes,
qui n'a pas de fiche **par conception** — lui en donner une ferait racheter les ingrédients du
repas qu'il recycle.

À défaut de marqueur, l'appariement par titre teste l'inclusion **dans les deux sens** : la fiche
est souvent plus détaillée que l'intitulé du menu. Il exige au moins douze caractères sur la
partie commune, seuil en dessous duquel un titre court comme « Œufs » s'accrocherait à n'importe
quel intitulé le mentionnant.

Quand rien ne correspond, le repas est **inséré quand même** avec `recipe_id = NULL`, et le motif
d'appariement retenu est stocké. Un slug explicite qui ne pointe nulle part est journalisé comme
`explicit_missing` plutôt que de retomber en silence sur l'heuristique.

## Conséquences

Des repas restent non reliés, et la liste de courses ignore leurs ingrédients. C'est visible —
le compteur `meals_orphan` et le `match_kind` le disent — là où une mauvaise liaison serait
invisible.

Le seuil de douze caractères est arbitraire et se paiera un jour sur un titre légitimement court.
Il est préférable au comportement sans seuil, qui rattachait des plats entiers à un mot commun.

Les marqueurs demandent une saisie manuelle à chaque menu. C'est le prix d'une liaison qui ne se
redérive pas.

## Alternatives écartées

**Apparier au plus proche voisin** (distance d'édition, similarité floue) : produit toujours une
réponse, donc rattache la mauvaise recette dès que la bonne est absente. L'erreur devient
silencieuse.

**Ne pas insérer les repas non reliés** : les ferait disparaître de partout, y compris des
manques signalés par la liste de courses — on ne saurait même plus qu'il faut cuisiner ce soir-là.

**Traiter un repas de restes comme un repas sans fiche** : produit une fausse alerte chaque
semaine, et une alerte qui revient toujours cesse d'être lue.
