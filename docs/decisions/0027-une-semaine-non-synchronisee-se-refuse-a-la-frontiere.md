---
numero: 0027
titre: Une semaine non synchronisée se refuse à la frontière de routage
statut: accepté
date: 2026-09-21
concerne:
  - backend/app.py
  - cooking_manager/presence.py
---

# 0027 — Une semaine non synchronisée se refuse à la frontière de routage

## Contexte

`ChildWeekUnknown` est levée quand la présence des enfants n'a jamais été synchronisée
avec gcal pour la semaine demandée. Ce n'est pas une erreur technique : c'est un refus de
répondre, et le `CLAUDE.md` du projet le dit — **409 ne veut jamais dire « enfants absents »**,
il veut dire « la question n'a pas été posée à gcal ».

`/api/attendance` la rattrapait dans un `try/except` local et rendait 409. Aucune autre route
ne le faisait. Or `attendees()` est appelée depuis au moins trois endroits, dont le calcul de
la liste de courses.

Mesuré le 2026-09-21 : `GET /api/menus/2026-09-01_semaine-aubagne/shopping-list` rendait
**500 Internal Server Error**. Deux menus sur six étaient inatteignables, et le 500 ne disait
rien du geste à faire — alors que l'exception, elle, porte le message complet avec l'endpoint
de synchronisation.

Le bug était antérieur à la session ; il a été révélé en ajoutant un **deuxième** site
d'appel de `week_grid()` dans la même route.

## Décision

Un `@app.exception_handler(ChildWeekUnknown)` au niveau de l'application rend **409** avec
le message de l'exception, pour **toutes** les routes. Le `try/except` local de
`/api/attendance` est supprimé : il faisait exactement la même chose, pour une seule route.

## Conséquences

- Toute route qui interroge la présence hérite du bon code sans rien écrire. Le site d'appel
  suivant — il y en aura — est couvert d'avance.
- La forme de la réponse est inchangée (`{"detail": …}`, celle de `HTTPException`) : aucun
  consommateur ne voit de différence sur la route qui marchait déjà.
- Vérifié après déploiement : `2026-09-01` et `2026-08-03` passent de 500 à 409,
  `/api/attendance` garde son 409, une semaine synchronisée garde son 200.
- La règle générale qu'on retient : **un refus de répondre appartient à la frontière**, pas
  à chaque route. Une garde répétée par route est une garde qu'on oubliera à la prochaine.

## Alternatives rejetées

**Ajouter un `try/except` dans `menu_shopping_list`.** Diff plus petit sur le moment, et
faux au fond : il aurait réparé le chemin nommé par le symptôme en laissant tous les
appelants frères cassés. C'est le motif que la doctrine de correction refuse — une garde
dans la fonction partagée est un diff plus petit qu'une garde dans chaque appelant.

**Faire de `ChildWeekUnknown` une `HTTPException`.** Elle serait alors un objet HTTP dans le
domaine pur, alors que `cooking_manager/` est sans I/O réseau par construction. La frontière
traduit ; le domaine ne connaît pas le transport.
