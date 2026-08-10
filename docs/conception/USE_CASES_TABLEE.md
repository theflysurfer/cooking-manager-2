---
title: Cas d'usage — Tablée (composition de table)
axis: usage
proof_level: provisional
upstream: [MOMENTS.md, ../marque/STAKEHOLDERS.md]
downstream: [julien-test-case-design]
status: draft
date: 2026-08-10
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
Seule couche entièrement modélisée aujourd'hui (`presence.py`).

| # | Situation | Couverture | Dimensions | Système actuel |
|---|---|---|---|---|
| 1 | Repas normal — tout le foyer à table | modélisé | T | `attendees()` trame déterministe |
| 2 | Enfants à la cantine (mar/jeu/ven, hors vacances) | modélisé | T | Slot `lunch` + jour + vacances |
| 3 | Vacances scolaires — enfants à la maison toute la semaine | modélisé | T | `is_school_holiday()` désactive la cantine |
| 4 | Semaine sans enfants (garde alternée) | modélisé | T | `children_present_this_week()` |
| 5 | Qui mange à quel repas cette semaine ? (lecture tablée) | partiel | T | API `/compatibility` renvoie `attendees`, pas d'écran dédié |

## B. Quelqu'un part — absences ponctuelles (6 cas)

Aujourd'hui : seul moyen = éditer `Presences.md` §Absences ou §Exceptions.
Pas d'interface, pas de granularité infra-journée.

| # | Situation | Couverture | Dimensions | Système actuel |
|---|---|---|---|---|
| 6 | Un parent en déplacement pro plusieurs jours | partiel | T | `Absence` dans `Presences.md` |
| 7 | Enfant malade, reste à la maison au lieu de la cantine | absent | T | Pas d'exception ponctuelle facile |
| 8 | Un enfant dort chez un copain (absent dîner + petit-déj) | absent | T | Pas modélisé |
| 9 | Julien jeûne — présent mais ne mange pas ce repas | absent | T | Pas de concept « à table mais ne mange pas » |
| 10 | Un parent déjeune au bureau ce midi | absent | T | Pas d'absence par créneau sans éditer le vault |
| 11 | Enfant en colonie de vacances une semaine | partiel | T | `Absence` dans `Presences.md` |

## C. Quelqu'un arrive — invités ponctuels (5 cas)

Aucun concept d'invité dans le système actuel. Les convives sont fixes
(déclarés dans `Convives.md`). Un invité n'a ni profil alimentaire ni
présence — il est invisible.

| # | Situation | Couverture | Dimensions | Système actuel |
|---|---|---|---|---|
| 12 | Les grands-parents viennent déjeuner dimanche (+2) | absent | T C | Pas de concept d'invité |
| 13 | Un copain de l'enfant dort à la maison (+1 dîner + petit-déj) | absent | T C | Pas modélisé |
| 14 | On invite 8 amis samedi soir (tablée ×3) | absent | T C | Pas modélisé, impact quantités |
| 15 | Un invité avec une allergie (noix, gluten…) | absent | T | Pas de profil alimentaire invité |
| 16 | L'invité annoncé ne vient plus — retirer | absent | T | Rien à retirer puisque rien n'est ajouté |

## D. Repas pris dehors — pas de cuisine (8 cas)

Le repas existe mais personne ne cuisine à la maison. Impact : pas de
consommation du garde-manger, pas de courses à faire pour ce créneau.
Aujourd'hui, le seul moyen de « supprimer » un repas est de ne pas le
mettre dans le menu — mais il reste dans la trame de présence.

| # | Situation | Couverture | Dimensions | Système actuel |
|---|---|---|---|---|
| 17 | Restaurant en famille | absent | T C L | Pas de concept « repas externe » |
| 18 | Invités chez des amis pour dîner | absent | T C L | Pas modélisé |
| 19 | Déjeuner chez les grands-parents (ils cuisinent) | absent | T C L | Pas modélisé |
| 20 | Goûter d'anniversaire d'un copain (enfant absent) | absent | T | Pas modélisé |
| 21 | Sortie scolaire avec pique-nique fourni par l'école | absent | T C | Pas modélisé |
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

Tout change : le lieu, la composition de la table, parfois qui cuisine.
C'est la catégorie du bug Bègles. Le système actuel ne connaît que
« à la maison » vs « absent » — un séjour avec cuisine est un angle mort.

| # | Situation | Couverture | Dimensions | Système actuel |
|---|---|---|---|---|
| 30 | Location de vacances — on cuisine pour 10 | absent | T C L | Bug : « Hors foyer, pas de repas » |
| 31 | Hôtel ou club vacances — pas de cuisine | partiel | T C L | Absence = hors foyer (confus mais fonctionnel) |
| 32 | Vacances chez les grands-parents — ils cuisinent | absent | T C L | Pas modélisé |
| 33 | Camping — cuisine sur place, matériel limité | absent | T C L | Pas modélisé |
| 34 | Road trip — restos et sandwichs | absent | T C L | Pas modélisé |
| 35 | Vacances en deux groupes — famille éclatée | absent | T C L | Pas modélisé |

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

| État | Nombre | Part |
|---|---|---|
| **Modélisé** | 4 | 10 % |
| **Partiel** | 5 | 12,5 % |
| **Absent** | 31 | 77,5 % |

La trame déterministe (A) fonctionne. Tout le reste — absences ponctuelles,
invités, repas dehors, vacances, hybrides — est un angle mort.

## Priorisation suggérée

1. **F.30** (séjour avec cuisine) — le bug actif, corrigé côté front mais pas modélisé
2. **B** (absences ponctuelles) — fréquence quotidienne, friction haute
3. **C** (invités) — impact direct sur les quantités et la compatibilité
4. **D** (repas dehors) — fréquent, empêche de calculer les vraies courses
5. **G** (hybrides) — cas limites, priorité basse
6. **E** (cuisine pour ailleurs) — rare, priorité basse
