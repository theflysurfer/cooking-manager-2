---
numero: 0023
titre: Une préférence déclare ce qu'elle ne sait pas mesurer
statut: accepté
date: 2026-09-21
concerne:
  - cooking_manager/preferences.py
  - backend/app.py
---

# 0023 — Une préférence déclare ce qu'elle ne sait pas mesurer

## Contexte

`dietary_preference` existait depuis des mois avec 11 règles (`minimize gluten`,
`rotate famille de protéine`, `cap sucres ajoutés 25 g/jour`…). Le `CLAUDE.md` du projet
le disait noir sur blanc : « ❌ rien ne le lit ». Les règles se composaient à la main,
donc elles ne se composaient pas.

En les branchant sur `/api/menus/{slug}/compatibility`, le premier rendu annonçait
**10 règles respectées sur 11**. Contrôle : 8 d'entre elles ne pouvaient rien mesurer.

- « famille de protéine », « gluten », « crucifère » ne sont portés par **aucun**
  `recipe_ingredient` : aucune ligne ne peut les faire monter, leur compte reste 0 à jamais.
- `cap sucres ajoutés 25 g/jour` est en **grammes** et le compteur compte des **repas**.
  Son « 0 / 25 » ne dit rien.
- « sucres ajoutés » matchait « compote **sans** sucres ajoutés » : une négation lue comme
  une présence.

Un zéro obtenu sans avoir pu mesurer se lit exactement comme un zéro mesuré.

## Décision

Toute règle rend `measurable: false` quand rien ne permet de la compter — cible absente du
vocabulaire des ingrédients, ou unité de `cap` qui n'est pas un repas. La réponse porte
`preferences_unmeasurable` **à côté** de `preferences_breached`, et les deux se lisent ensemble.

Une cible peut être une CLASSE connue (`protéine animale`, `famille de protéine`) résolue par
le code vers ses termes ; une classe rend la règle mesurable, une catégorie inventée non.

## Conséquences

- Le tableau de bord devient moins flatteur : 8 règles sur 10 s'affichent aveugles. C'est le but.
- `rotate famille de protéine` compte désormais **par famille** (viande, volaille, poisson,
  fruits de mer, œuf, légumineuse), ce qui demande une table de familles maintenue dans le code.
- Les règles aveugles restent à appliquer à la main : la mesure ne les répare pas, elle les nomme.
- Une cible mal orthographiée devient silencieusement `measurable: false` au lieu de lever :
  c'est un défaut assumé, l'alternative (refuser la règle) bloquerait la composition d'un menu.

## Alternatives écartées

- **Laisser l'absence valoir « respecté »** — c'est l'état d'avant, et il ment sans erreur.
- **Refuser en base une préférence non mesurable** — `minimize gluten` est une vraie règle du
  foyer même si aucun ingrédient ne porte le mot « gluten ». La bannir la ferait disparaître
  au lieu de la signaler.
- **Inférer la cible par un LLM au moment du contrôle** — introduit une dépendance réseau dans
  un calcul qui doit être rejouable, et rend non reproductible un chiffre qu'on veut opposable.
