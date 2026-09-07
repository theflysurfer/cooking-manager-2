# 0006 — Un quatrième verdict de rejeu : le plat lié à une occasion

- **Statut** : accepté
- **Date** : 2026-09-07
- **Supersède** : rien. Étend `replay_verdicts` posé par l'ADR 0005.

## Contexte

La première revue rétro réelle a produit six retours de table. Deux d'entre eux
disent la même chose, et aucun des trois verdicts existants ne sait la porter :

- « Sandwiches saumon fumé samouraï : c'est très bon, mais **à réserver pour les
  pique-niques**. »
- « Saumon grillé, lentilles vertes et poêlée : c'est très moyen, **à ne refaire
  que quand il faut finir les restes**. »

`keep_as_is` dit « le plat rentre dans la rotation sans modification » — faux :
il ne se propose pas librement. `adjust` exige un `issue_kinds` — or ces plats
n'ont rien à corriger, ils sont bons. `retire` les sortirait du répertoire alors
qu'ils y restent utiles.

Sans quatrième cran, la condition disparaît du calcul : le moteur reproposerait
les sandwiches un mardi soir comme n'importe quel plat gardé. La contrainte
existerait dans le verbatim, lisible par un humain, invisible à toute décision —
la famille « un signal absent n'est pas un signal vert ».

## Décision

`situational` — « À refaire pour une occasion précise ». Le plat reste au
répertoire mais est lié à un **contexte de service**, pas à un défaut.

L'occasion elle-même n'entre pas dans le vocabulaire : elle vit dans le
`verbatim`. Une taxonomie d'occasions (pique-nique, vide-frigo, réception,
lendemain de fête) construite sur deux observations serait inventée, pas mesurée
— exactement le défaut que l'ADR 0002 reproche à une dominance plausible.

Deux gardes rendent le concept faillible plutôt que décoratif :

- `POST /api/recipes/{slug}/verdict` refuse (422) un `situational` sans
  `verbatim` : sans occasion nommée, le verdict ne dit rien.
- Les synonymes déclarés (« à réserver pour », « seulement quand », « quand il
  faut finir ») sont plus longs que ceux de `keep_as_is`, donc ils gagnent — la
  même mécanique de longueur qui sépare déjà « à refaire en modifiant » de
  « à refaire ».

## Conséquences

- `cooking-vocabulary` passe en **v0.5.0** : ajout d'un concept, non cassant pour
  les consommateurs qui itèrent la facette, cassant pour tout code qui aurait
  énuméré trois clés en dur. Aucun n'existe à ce jour.
- Le futur moteur de composition de menu doit traiter `situational` comme un
  **retrait de la proposition libre**, pas comme un `keep_as_is` affaibli.
- Statut `probation` : mesuré sur **2 occurrences**. Deux ne trient rien. Il
  passera `active` quand l'usage l'aura confirmé, ou sera retiré s'il se révèle
  n'être qu'un `adjust` mal formulé.

## Alternatives écartées

**`keep_as_is` + occasion en verbatim.** Zéro concept nouveau, mais la condition
devient invisible au calcul : c'est précisément la perte qu'on cherche à éviter.

**Un axe `occasions` séparé.** Plus expressif, mais il faudrait le peupler
d'avance sur deux observations. Le verbatim garde l'information sans prétendre
la classer.
