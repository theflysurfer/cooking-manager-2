# 0019 — Apparier un ingrédient à sa fiche, et la forme par défaut est crue

- **Statut** : accepté
- **Date** : 2026-09-11
- **Porte** : `cooking_manager/nutrition.py`, `cooking_manager/ingredients.py`
- **Issues** : #65
- **Voir aussi** : ADR 0011 (un import ne tranche pas, il déclare), ADR 0013 (ce que la normalisation retire), ADR 0014 (les dispositions de fiche que le lecteur sait lire)

## Contexte

Le moteur de macros rendait 7 à 25 % de couverture sur **toutes** les recettes,
existantes comprises. Un total présenté sur un quart des ingrédients est le
« nombre faux crédible » : il paraît complet et ne l'est pas. Quatre causes
distinctes, toutes mesurées (diagnostic complet dans #65).

Deux d'entre elles demandaient une décision, pas seulement un correctif :

1. **Comment un ingrédient de recette rencontre sa fiche.** L'appariement ne
   marchait que si l'ingrédient *commençait par* la clé de la fiche. « riz basmati
   complet » ne trouvait donc pas « riz complet ». Le sens inverse — « patate
   douce » attrapant une fiche plus spécifique « patate douce cuite » — est un
   piège : appliquer des macros cuites (facteur ~3) à un poids pesé cru, en
   silence.

2. **Quelle forme choisir quand la recette ne nomme pas l'état.** Une fiche à
   plusieurs colonnes (crues / cuites) laissait l'ingrédient non nommé en
   « forme ambiguë → non résolu » (Règle 1, ADR 0011). Résultat : chaque féculent
   ou légume à double forme tombait de la couverture.

## Décision

**Appariement par sous-ensemble de mots, la clé la plus spécifique gagne.**
Une fiche s'applique si **tous** les mots de sa clé sont présents dans le nom de
l'ingrédient. Entre plusieurs fiches candidates, celle qui a le plus de mots
gagne (départage : préséance marque < drive < générique). « riz basmati
complet » trouve « riz complet » ; « patate douce cuite » (3 mots) ne peut pas
matcher « patate douce » nu (2 mots) — le sens dangereux est fermé par
construction, sans garde séparée.

**La forme par défaut est crue.** Quand la recette ne nomme pas l'état, le
moteur retient la colonne crue si la fiche en a une. Une recette pèse ses
ingrédients crus ; les macros se conservent à cette masse. Faute de colonne
crue, la fiche reste ambiguë (on ne devine pas entre deux cuissons, ex. grillé
vs rôti).

Cette décision **remplace** le comportement antérieur où une forme non nommée
restait « non résolue ». La Règle 1 (pas d'hypothèse, ADR 0011) tient toujours
pour tout le reste : ce n'est pas une hypothèse mais une convention de pesée.

## Conséquences

- « riz basmati complet », « lentilles » (→ crues), « blanc de poulet » (→ cru)
  se résolvent désormais ; la couverture double à triple sur les recettes réelles.
- Une fiche dont **l'état est dans le nom de fichier** (`patate-douce-cuite.md`,
  ~19 fiches) ne matche plus un ingrédient nu : elle sort « aucune fiche
  aliment ». C'est **voulu** — ces fiches doivent migrer vers une fiche par
  aliment portant l'état en colonne (chantier data #65, étapes 1 et 5). Le moteur
  ne fabrique pas un chiffre faux en attendant.
- Le résidu non résolu est maintenant exactement le travail de référentiel qui
  reste : fiches manquantes (brocoli, chou-fleur, poireau, oignon, ail, citron,
  pulpe de tomate…) et fiches à état à migrer.

## Corollaires branchés dans le même chantier

Deux correctifs sans décision, notés ici pour la traçabilité :

- **Unités comptées.** Le poids écrit entre parenthèses de la ligne
  (« 2 courgettes (environ 300 g) », en g ou ml) est lu en priorité ; sinon une
  table de poids moyen par pièce (`GRAMS_PER_PIECE`) couvre les légumes courants.
  C'est une table de **calibration** (le monde physique varie) : à affiner sur
  pesée réelle, à étendre au besoin.
- **Assaisonnements.** Sel, poivre, herbes et épices (`NEGLIGIBLE`) sortent du
  dénominateur de couverture : leurs macros sont négligeables, les compter comme
  non résolus faussait la mesure.
- **Pluriels en -eaux / -oux.** `_singular` ne retirait que le -s : « poireaux »
  ne devenait jamais « poireau ». Corrigé pour -eaux → -eau et -oux → -ou, à la
  racine partagée (l'appariement du garde-manger et de la compatibilité en
  profitent aussi).
