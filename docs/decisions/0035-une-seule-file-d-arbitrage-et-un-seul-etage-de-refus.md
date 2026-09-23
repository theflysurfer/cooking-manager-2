---
numero: 0035
titre: Une seule file d'arbitrage, et un seul étage de refus
statut: accepté
date: 2026-09-23
concerne:
  - cooking_manager/linking.py
  - backend/app.py
  - backend/db.py
  - data/ontology/cooking-vocabulary.yaml
supersede_partiellement: 0032
---

# 0035 — Une seule file d'arbitrage, et un seul étage de refus

## Contexte

L'ADR 0032 décrit une file d'arbitrage pour un seul sujet : rattacher un libellé à un aliment
(`food_key`). L'ADR 0033 a, le même mois, ouvert un second sujet de même nature — qualifier un
aliment d'une famille (`food.kind`), axe fermé du vocabulaire. Mesuré le 2026-09-23 avant
travaux : **176 aliments sur 191 sans famille**, **330 lignes de stock et 1169 ingrédients de
recette sans `food_key`**.

Les deux sujets posent exactement la même question — *quelle valeur du référentiel, parmi ces
candidats, et que faire quand aucune ne s'impose ?* — et appellent la même réponse : proposer,
ne jamais élire d'office, et nommer ce qu'on n'a pas su trancher. Deux files auraient été la
même mécanique écrite deux fois, avec deux occasions d'oublier un compteur.

La cascade de l'ADR 0032 prévoyait par ailleurs quatre étages, dont un **jugement par Claude via
l'API HTTP Ollama**. À l'écriture, deux constats : la file a déjà deux portes, Claude Code
pendant la course et `web/` à tête reposée — soit le même jugement, rendu par un modèle qui a lu
la base ; et un refus par étage multiplie les endroits où « je n'ai pas su » peut se dire
différemment, donc se lire mal.

## Décision

1. **Une file, deux sujets.** La table `arbitration` porte `subject` (`food_key` | `food_kind`),
   `scope`, `ref`, ses `candidates` scorés et son `reason`. `UNIQUE (subject, scope, ref)` : un
   arbitrage rendu ne se redemande jamais.
2. **Un seul étage tranche : l'exact.** Égalité des mots porteurs après normalisation, et un
   seul candidat. Tout le reste — zéro candidat, plusieurs exacts, une inclusion, un
   recouvrement — passe par l'unique fonction de refus, qui classe les candidats et dit pourquoi.
3. **`settled` avec `decision NULL` veut dire « instruit, hors référentiel »**, et c'est ce qui
   le distingue d'un sujet jamais vu. L'API rend **422** sur un refus sans motif : un `NULL`
   sans raison se lit comme un oubli, pas comme un jugement.
4. **Une famille qui en `dominates` d'autres ne se pose jamais d'office.** Le rayon « poissons »
   ferait élire `fish` par égalité de nom ; le critère 5 du cadre méditerranéen, qui compte le
   poisson **gras**, lirait alors zéro sans jamais dire pourquoi. `fish` domine
   `oily-fish`/`lean-fish`, `grain` domine `whole-grain`/`refined-grain`. Le champ existait déjà
   dans le schéma d'ontologie et était validé ; il ne restait qu'à le poser.
5. **L'étage de jugement automatique n'est pas câblé.** Le seam reste ouvert :
   `Candidate.origin` accepte une provenance, et un arbitre automatique s'ajouterait entre les
   candidats et le refus sans toucher au reste.

## Conséquences

- Le rattrapage s'est fait en trois passes le 2026-09-23. Après elles : 183 lignes de stock et
  701 ingrédients rattachés, 155 aliments qualifiés, **695 entrées tranchées dont 179 refus
  motivés**, et 150 en attente.
- `GET /api/menus/{slug}/mediterranean` est passé de `measured: false` à `measured: true`.
- Les 150 en attente ne sont pas des arbitrages en souffrance : 114 demandent une fiche `food`
  qui n'existe pas (#144), 36 une valeur de `food_kinds` qui n'existe pas (#145). Les trancher
  ferait mentir les macros ou la couverture.
- `POST /api/shopping/validate-cart` rend `ok: false` sur une ligne jamais confrontée au
  référentiel, et la nomme. Ce gate s'empile sur celui des bans et sur l'ADR 0028.
- Un arbitrage porte sur un **libellé normalisé**, pas sur une ligne : une décision couvre d'un
  coup toutes les lignes de stock et tous les ingrédients qui le portent. C'est ce qui ramène
  1499 lignes à quelques centaines de décisions.

## Alternatives écartées

- **Deux files, une par sujet** : la même mécanique écrite deux fois, et deux occasions d'oublier
  d'exposer le compteur en attente.
- **Laisser l'inclusion trancher seule** (tous les mots de l'aliment présents dans le libellé) :
  ferait de « lait de coco » un « lait » dès que la fiche « lait de coco » manque. Un faux
  rattachement est pire qu'une entrée en file, parce qu'il porte des macros.
- **Câbler l'arbitre Ollama tout de suite** (ADR 0032, point 2) : ajoute une dépendance réseau
  et un second chemin de jugement avant d'avoir mesuré que l'arbitrage manuel est le goulot.
- **Trancher `kind` pour les 36 aliments sans famille applicable** : écrire « hors référentiel »
  là où la famille existe mais manque au vocabulaire ferait passer une lacune pour une décision.
