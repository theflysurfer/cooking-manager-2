---
title: Cas d'usage — Tablée (composition de table)
axis: usage
proof_level: provisional
upstream: [MOMENTS.md, ../marque/STAKEHOLDERS.md]
downstream: [julien-test-case-design]
status: draft
date: 2026-08-10
recount: 2026-09-03
---

# Cas d'usage — Tablée

> **Tablée** = qui mange à ce repas. Pas « qui est à la maison » — le lieu ne
> décide de rien. Un repas planifié a lieu ; la tablée dit juste qui est dedans.
>
> Incident fondateur : Bègles, 2026-08-10. La famille cuisine pour 10 en location
> de vacances. L'app affiche « Hors foyer — pas de repas à préparer » pour les
> 4 jours du menu, parce que `Presences.md` les déclare « absents ».

## Les trois dimensions indépendantes

| Dimension | Question | Impact système |
|---|---|---|
| **Tablée** (T) | Qui mange ? | Compatibilité alimentaire, nombre de couverts |
| **Cuisine** (C) | Qui prépare ? | Consommation garde-manger, liste de courses |
| **Lieu** (L) | Où mange-t-on ? | Informatif — aucun impact calcul |

Le système actuel ne modélise que `at_home: true/false`, qui mélange les trois.

> **Recompte du 2026-09-03.** Les couvertures ci-dessous datent du 2026-08-10,
> avant le câblage `stay`/`stay_member` du 2026-08-12 (refs #33) qui a rendu la
> présence 100 % DB. Chaque ligne a été relue contre le schéma réel
> (`backend/db.py`), le résolveur (`presence.py::attendees()`) et les routes
> exposées. La dimension **T** (qui mange) a beaucoup avancé ; la dimension **C**
> (qui cuisine) n'a pas bougé d'un cas.

## Rôle associé

**R8. Le régisseur** — gère qui est à table

> *Quand la composition de la table change (invité, absent, vacances), je veux
> déclarer qui mange à quel repas, afin que les quantités et la compatibilité
> soient justes sans que je recalcule de tête.*

- **Situation/contrainte** : la composition change en cours de semaine (parfois
  en cours de journée). Le régisseur a besoin de modifier un repas précis, pas
  de reconfigurer toute la semaine.

## Familles de scénarios engendrés

| SC | Slug | Catégorie source | Rôle |
|---|---|---|---|
| SC-25 | `trame-tablee` | A — Trame de base | R8 |
| SC-26 | `absence-ponctuelle` | B — Quelqu'un part | R8 |
| SC-27 | `invite-ponctuel` | C — Quelqu'un arrive | R8 |
| SC-28 | `repas-externe` | D — Repas dehors | R8 × R1 |
| SC-29 | `cuisine-emportee` | E — Cuisine pour ailleurs | R8 × R2 |
| SC-30 | `sejour-cuisine` | F — Vacances (on cuisine) | R8 × R1 |
| SC-31 | `sejour-sans-cuisine` | F — Vacances (pas de cuisine) | R8 |
| SC-32 | `repas-hybride` | G — Cas hybrides | R8 |

---

## A. Trame de base — composition habituelle (5 cas)

La trame déterministe : garde alternée × vacances scolaires × cantine.
Entièrement modélisée, et désormais **entièrement en DB** (`custody_schedule`,
`school_period`) — les constantes `ADULTS`/`CHILDREN`/`CUSTODY_REFERENCE_WEEK`
ne servent plus que de repli quand aucune `HouseholdConfig` n'est fournie.

| # | Situation | Couverture | Dimensions | Système actuel |
|---|---|---|---|---|
| 1 | Repas normal — tout le foyer à table | modélisé | T | `attendees()` trame déterministe |
| 2 | Enfants à la cantine (mar/jeu/ven, hors vacances) | modélisé | T | `canteen_schedule` en DB, `_child_at_canteen()` |
| 3 | Vacances scolaires — enfants à la maison toute la semaine | modélisé | T | `school_period` en DB, `is_school_holiday()` |
| 4 | Semaine sans enfants (garde alternée) | modélisé | T | `custody_schedule` par enfant (rythme et date de référence propres) |
| 5 | Qui mange à quel repas cette semaine ? (lecture tablée) | partiel | T | `GET /api/attendance?day=&slot=` résout ; **aucun écran front** |

## B. Quelqu'un part — absences ponctuelles (6 cas)

Rattrapée par la table `absence` (`POST`/`GET`/`DELETE /api/absences`), dont le
`slot` nullable donne la granularité infra-journée qui manquait. Reste le point
aveugle symétrique : une absence sait **retirer** quelqu'un, jamais l'ajouter.

| # | Situation | Couverture | Dimensions | Système actuel |
|---|---|---|---|---|
| 6 | Un parent en déplacement pro plusieurs jours | modélisé | T | `absence` multi-jours, `slot` NULL |
| 7 | Enfant malade, reste à la maison au lieu de la cantine | absent | T | Il faut **ajouter** l'enfant au déjeuner — seul un override le ferait, et rien n'écrit `meal_attendance` |
| 8 | Un enfant dort chez un copain (absent dîner + petit-déj) | modélisé | T | Deux `absence` par créneau sur deux jours |
| 9 | Julien jeûne — présent mais ne mange pas ce repas | modélisé | T | `absence` avec `slot` — « pas à table pour ce repas » est exactement la sémantique |
| 10 | Un parent déjeune au bureau ce midi | modélisé | T | `absence` `slot='lunch'`, un seul jour |
| 11 | Enfant en colonie de vacances une semaine | modélisé | T | `absence` multi-jours |

## C. Quelqu'un arrive — invités ponctuels (5 cas)

Le concept d'invité **existe maintenant** : `person.circle`
(`extended_family`/`friend`/`occasional`) porte les profils, et
`load_convives_from_db()` les rend à `check_meal` comme n'importe quel convive
(mesuré le 2026-09-03 : 10 personnes en `extended_family`, 4 en `household`).
Ce qui manque n'est plus le profil — c'est **le geste qui met l'invité à table
pour un repas donné**. Cf. § Le chaînon manquant.

| # | Situation | Couverture | Dimensions | Système actuel |
|---|---|---|---|---|
| 12 | Les grands-parents viennent déjeuner dimanche (+2) | partiel | T C | Profils en base ; aucun moyen de les mettre à table pour **un** repas |
| 13 | Un copain de l'enfant dort à la maison (+1 dîner + petit-déj) | partiel | T C | Idem — profil créable, mise à table impossible |
| 14 | On invite 8 amis samedi soir (tablée ×3) | absent | T C | `meal_attendance.extra_headcount` existe en colonne, **ni écrit ni lu** |
| 15 | Un invité avec une allergie (noix, gluten…) | partiel | T | `person.forbidden`/`dislikes` couvrent le profil ; inutile tant qu'il n'est pas à table |
| 16 | L'invité annoncé ne vient plus — retirer | partiel | T | Une `absence` le retirerait, mais rien ne l'avait ajouté |

## D. Repas pris dehors — pas de cuisine (8 cas)

Le repas existe mais personne ne cuisine à la maison. Impact : pas de
consommation du garde-manger, pas de courses à faire pour ce créneau.
Aujourd'hui, le seul moyen de « supprimer » un repas est de ne pas le
mettre dans le menu — mais il reste dans la trame de présence.

| # | Situation | Couverture | Dimensions | Système actuel |
|---|---|---|---|---|
| 17 | Restaurant en famille | absent | T C L | Vider la tablée par des `absence` en cascade n'est pas déclarer un repas externe |
| 18 | Invités chez des amis pour dîner | absent | T C L | Pas modélisé |
| 19 | Déjeuner chez les grands-parents (ils cuisinent) | absent | T C L | Pas modélisé |
| 20 | Goûter d'anniversaire d'un copain (enfant absent) | modélisé | T | `absence` `slot='snack'` |
| 21 | Sortie scolaire avec pique-nique fourni par l'école | modélisé | T C | `absence` `slot='lunch'` — la tablée est juste, le pique-nique n'est pas un objet |
| 22 | Festival, food trucks, marché de nuit | absent | T C L | Pas modélisé |
| 23 | Cérémonie, mariage — repas traiteur | absent | T C L | Pas modélisé |
| 24 | Brunch au resto qui remplace petit-déj + déjeuner | absent | T C L | Pas de fusion de créneaux |

## E. Cuisine pour ailleurs (5 cas)

On cuisine à la maison, mais on ne mange pas à la maison. Impact :
consomme le garde-manger et génère des courses, mais la tablée est
ailleurs (pas de vaisselle, pas de table à mettre). Aucun de ces cas
n'est modélisé.

| # | Situation | Couverture | Dimensions | Système actuel |
|---|---|---|---|---|
| 25 | Pique-nique — cuisiner puis manger au parc | absent | C L | Pas modélisé |
| 26 | Gamelle pour le bureau (meal prep du midi) | absent | C | Pas modélisé |
| 27 | Plat à amener chez des amis (chacun apporte un truc) | absent | C | Pas modélisé |
| 28 | Gâteau d'anniversaire à préparer pour l'école | absent | C | Pas modélisé |
| 29 | BBQ chez des amis — on apporte viande et salade | absent | C L | Pas modélisé |

## F. Vacances et séjours (6 cas)

**La catégorie qui a le plus bougé.** `stay` + `stay_member` (2026-08-12)
corrigent le bug fondateur : les membres d'un séjour sont à table quels que
soient la trame et les absences (`attendees()`, niveau 2). Le drapeau
`stay.cooking` est en revanche **exposé sans être consommé** — `/api/attendance`
le renvoie, aucun calcul de courses ni de garde-manger ne le lit. Un séjour à
l'hôtel produit donc toujours une liste de courses.

| # | Situation | Couverture | Dimensions | Système actuel |
|---|---|---|---|---|
| 30 | Location de vacances — on cuisine pour 10 | modélisé | T C L | `stay` `cooking=true` + `stay_member` — le séjour Bègles est en base |
| 31 | Hôtel ou club vacances — pas de cuisine | partiel | T C L | `stay` `cooking=false` : tablée juste, **courses générées quand même** |
| 32 | Vacances chez les grands-parents — ils cuisinent | partiel | T C L | Idem — `cooking=false` déclaré, jamais lu |
| 33 | Camping — cuisine sur place, matériel limité | modélisé | T C L | `stay` `cooking=true` ; la contrainte matériel est hors dimensions T/C |
| 34 | Road trip — restos et sandwichs | partiel | T C L | `stay` `cooking=false`, même angle mort qu'en 31 |
| 35 | Vacances en deux groupes — famille éclatée | absent | T C L | Deux `stay` chevauchants : `stay_covering()` renvoie **le premier trouvé**, silencieusement |

## G. Cas hybrides et limites (5 cas)

Situations qui ne rentrent dans aucune catégorie simple. Elles testent
les bords du modèle.

| # | Situation | Couverture | Dimensions | Système actuel |
|---|---|---|---|---|
| 36 | Commande livrée (pizza, Uber Eats) — on mange chez soi sans cuisiner | absent | C | Pas de concept « repas sans cuisine » |
| 37 | Restes réchauffés — pas de cuisine neuve | partiel | C | Tag `_leftovers` dans le menu |
| 38 | Meal prep du dimanche — cuisiner 5 repas, n'en manger qu'un | absent | C | Pas modélisé |
| 39 | Deux tablées au même créneau — dîner enfants tôt, adultes tard | absent | T | Un créneau = une tablée, pas de split |
| 40 | Invité qui apporte le plat — on mange chez soi, quelqu'un d'autre a cuisiné | absent | T C | Pas modélisé |

---

## Couverture globale

Recomptée le **2026-09-03**, ligne à ligne contre le schéma et les routes.

| État | 2026-08-10 | 2026-09-03 |
|---|---|---|
| **Modélisé** | 4 (10 %) | **13 (32,5 %)** |
| **Partiel** | 5 (12,5 %) | **9 (22,5 %)** |
| **Absent** | 31 (77,5 %) | **18 (45 %)** |

Par famille : A 4/5 · B 5/6 · C 0/5 (4 partiels) · D 2/8 · E 0/5 · F 2/6
(3 partiels) · G 0/5.

**La dimension T a été traitée, la dimension C n'a pas bougé.** Les 9 cas gagnés
disent tous *qui mange* ; aucun ne dit *qui cuisine*. Les cinq cas de la famille
E restent à zéro depuis le premier jour, et les trois partiels de F le sont pour
la même raison — `stay.cooking` est le seul endroit du modèle où « on cuisine ou
non » est écrit, et rien ne le lit.

## Le chaînon manquant : `meal_attendance` n'a aucune écriture

`presence.py::attendees()` place l'**override manuel au sommet** de la
hiérarchie, et `load_referential_from_db()` va bien le chercher dans
`meal_attendance` (`source IN ('manual','voice')`). Mais **aucune route, aucun
intent vocal, aucun code n'écrit jamais dans cette table** — vérifié par
recherche sur tout le dépôt, et mesuré en prod le 2026-09-03 : `meal_attendance`
contient **0 ligne**. La couche prioritaire du résolveur est donc inatteignable.

C'est ce qui bloque toute la famille C d'un seul coup : les profils d'invités
existent, le résolveur saurait les prendre, il manque le geste qui les inscrit.
Même cause pour B.7 (ajouter quelqu'un qu'une absence ne sait que retirer) et
G.39 (deux tablées au même créneau).

Deux colonnes mortes au passage, à traiter avec : `extra_headcount` (les invités
anonymes, C.14) n'est ni écrit ni lu, et `stay.cooking` est lu par
`/api/attendance` sans qu'aucun calcul n'en tienne compte.

## Priorisation révisée (2026-09-03)

1. **Écrire `meal_attendance`** — `POST /api/attendance` + intent vocal. Débloque
   C.12/13/15/16, B.7, G.39 d'un seul geste, et rend enfin joignable la couche
   déjà écrite dans le résolveur.
2. **Consommer `stay.cooking`** dans les courses et le garde-manger — corrige
   F.31/32/34, qui aujourd'hui font faire des courses pour un hôtel.
3. **`extra_headcount`** — C.14, quantités pour les invités anonymes.
4. **Modéliser le repas externe** (famille D, 6 cas restants) — la dimension C
   d'un repas, distincte de celle d'un séjour.
5. **Séjours chevauchants** (F.35) — `stay_covering()` tranche en silence.
6. **E** (cuisine pour ailleurs) et **G** (hybrides) — priorité basse, inchangé.
