# Corpus web — ce qu'il a révélé du moteur de substitutions

> 34 recettes du web, dont 25 exploitables et **4 carnées**. Les carnées sont le
> vrai test : elles ont trouvé deux défauts qu'aucune recette du vault ne pouvait
> montrer, parce que le vault est déjà adapté au foyer.
>
> **La mesure d'extraction elle-même a été rapatriée le 2026-09-03** dans
> `recipe-manager/docs/CORPUS_WEB.md` (banc : `scripts/measure_parse_url.py`),
> avec le dépôt qui porte la cascade. Ce qui reste ici est ce qui appartient au
> moteur de CM2.
>
> Le corpus du vault (`CORPUS_ACCOMMODATIONS.md`) mesure la **pratique du foyer**.
> Celui-ci sert à autre chose : éprouver le moteur sur des recettes **hostiles** —
> carnées, rédigées par d'autres, non adaptées.

## Défaut 1 — une règle de cuisine débordait sur les autres · CORRIGÉ (2026-09-02)

`score_rule()` ajoutait un bonus quand la cuisine d'une règle matchait, mais **ne
pénalisait pas** le cas contraire : la priorité de base décidait seule. La règle
ouest-africaine (priorité 97) s'appliquait donc à **tout** mijoté de poulet —
rendant sur un « Poulet en cocotte au vin blanc » la raison visible
« *Le mafé du foyer se fait déjà au cabillaud* ».

Corrigé par `rule_applies()` : une règle qui **déclare** des cuisines ne vaut que
dans ces cuisines, dès lors que le plat en nomme une. Une règle sans cuisine
déclarée reste le filet, et un plat sans cuisine détectée ne perd aucune règle.

## Défaut 2 — « faire revenir » faisait gagner la mauvaise règle · CORRIGÉ (2026-09-03)

« Cocotte de poulet mijoté de ma grand-mère » rendait **dorade**, « poisson
méditerranéen classique ». Le décompte d'alors :

| Règle | priorité | bonus cuisine | bonus cuisson | total |
|---|---|---|---|---|
| dorade *(grilled, oven, **pan-fried**)* | 90 | +20 | **+40** | **150** |
| lotte *(**stew**, slow-cooked)* | 95 | +0 | +40 | 135 |

Le contexte détectait `('stew', 'slow-cooked', 'pan-fried')` : `pan-fried` venait
de « **faites revenir** les morceaux de poulet », l'étape de saisie que porte
**tout** mijoté. Une dorade grillée gagnait donc sur une lotte mijotée, dans une
cocotte.

Même défaut structurel que « l'étape de garniture pilote le plat », corrigé côté
accommodation : **une étape préparatoire n'est pas le mode de cuisson du plat.**

**Parade retenue — la dominance, portée par le vocabulaire.** Un mode de cuisson
déclare ce qu'il absorbe (`dominates`, vocabulaire v0.3.0) ; `drop_dominated()`
retire du contexte les modes absorbés avant tout scoring. `stew` et `slow-cooked`
dominent `pan-fried`, `pan-seared` et `stir-fry` : on ne poêle pas un bœuf
bourguignon, on le fait revenir avant de le mijoter.

Vérifié en production le 2026-09-03 sur `mafe-poulet`, qui contient « faire
revenir les oignons » **et** « saisir les crevettes » :
`/api/recipes/mafe-poulet/compatibility` rend `cooking_methods: ["stew"]` seul.
Alternatives écartées : pondérer selon la position de l'étape (dépend de l'ordre
de rédaction, fragile sur une fiche importée) et dégrader le bonus des modes
suivants (arbitraire — le « premier » dépend de l'ordre du vocabulaire).

⚠️ La table de dominance ne porte **que ce qui a été mesuré**. `oven` dominant
`pan-seared` (saisir puis enfourner) est plausible et n'a pas été observé : l'y
inscrire serait le défaut reproché à `separate_dish`.

## Manque de lexique constaté · OUVERT

`canard` (« Salade de lentilles aux crevettes », qui contient du magret) n'est
**aucune** `source` de règle : la recette ressort sans réparation possible, sans
que rien ne le dise.

## Filtrage selon les profils — attention au faux positif

Le tri par `person.dislikes` est piégeux. Un premier passage signalait **15
recettes sur 25** portant des « olives ». Après vérification : **1 seule** en
porte vraiment (« Poulet aux olives », 100 g d'olives noires). Les autres étaient
de l'**huile** d'olive — `olive oil` chez Ricardo, que l'exclusion française ne
rattrapait pas.

Une aversion se cherche sur l'**ingrédient**, jamais sur une sous-chaîne du
texte. Même famille que « citron » qui matchait « citronnelle », et que
« Julien » dans « julienne ».
