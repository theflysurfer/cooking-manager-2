---
numero: 18
titre: "Une entrée d'API refuse les champs qu'elle ne connaît pas"
statut: accepte
date: 2026-09-09
supersede: null
---

# 0018 — Une entrée d'API refuse les champs qu'elle ne connaît pas

## Contexte

Le 2026-09-09, marquer un repas comme mangé a échoué sans le dire.

L'appel `PATCH /api/menus/{slug}/meals/{id}` portait `{"served": true}`. Il a rendu
`200` avec un objet de repas d'apparence normale. `menu_meal.served` est resté `NULL`.

`MealUpdate` ne déclare que `recipe_slug`, `dish` et `covers`. Pydantic ignore les
champs supplémentaires par défaut : le corps a été accepté, le champ silencieusement
écarté, et aucune branche du handler n'a écrit quoi que ce soit.

La réponse contenait par ailleurs `recipe_id: null` — la valeur d'une variable locale
non renseignée, pas l'état de la base, qui portait une liaison intacte. Elle **se lit
comme une liaison détruite**, et a envoyé le diagnostic sur la mauvaise piste.

C'est la famille « signal absent » : la valeur rendue est la même que si tout allait
bien.

## Décision

**Tout modèle pydantic d'entrée porte `model_config = ConfigDict(extra="forbid")`.**

Un champ que le modèle ne connaît pas fait rendre `422` avec son nom, au lieu d'être
avalé. Le coût est nul, le gain est qu'une erreur d'appel se voit à l'appel.

**Corollaire** : une réponse ne présente pas une variable locale comme un état de la
base. Ce qu'un handler n'a pas lu ou pas écrit ne figure pas dans ce qu'il rend, ou y
figure relu depuis la base.

## Conséquences

- Un client qui envoyait un champ superflu et l'ignorait sans le savoir reçoit
  désormais une erreur. C'est l'effet recherché : ce client se trompait déjà.
- `served` s'écrit par `POST /api/menus/{slug}/served`, qui désigne les repas par
  `day` / `slot` / `position`. C'est la seule route qui touche cette colonne.
- Deux modèles ne peuvent plus se recouvrir partiellement en silence : une clé qui
  change de nom casse à l'appel, pas trois écrans plus loin.

## Alternatives écartées

- **Ajouter `served` à `MealUpdate`.** Deux routes écriraient la même colonne avec
  deux modes de désignation (par id, par jour+créneau). Le décommissionnement d'une
  source doit retirer ses écrivains, pas les multiplier (ADR 0010).
- **Journaliser les champs inconnus sans refuser.** Un log que personne ne lit est un
  garde-fou qui ne sait pas échouer.
