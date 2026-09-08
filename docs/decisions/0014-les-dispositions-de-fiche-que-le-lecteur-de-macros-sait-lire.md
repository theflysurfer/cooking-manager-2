# 0014 — Les dispositions de fiche que le lecteur de macros sait lire

- **Statut** : accepté
- **Date** : 2026-09-08
- **Porte** : `cooking_manager/nutrition.py`
- **Issues** : #71
- **Voir aussi** : ADR 0011 (un import ne tranche pas, il déclare)

## Contexte

Le référentiel du Coach Nutrition n'a jamais eu de gabarit imposé. Les fiches ont
été écrites au fil de trois ans, dans des dispositions différentes — et une
disposition non reconnue ne produit **aucune erreur** : la fiche est simplement
absente du calcul.

C'est la panne la plus coûteuse de ce module : un total de macros qui paraît
complet alors qu'il a été calculé sans un tiers du corpus.

## Décision

### 1. Trois dispositions sont reconnues, et elles ont été mesurées

| Disposition | Forme | Ce qui se passait avant |
|---|---|---|
| **Colonnes de métriques** | `\| Métrique \| /100g \| 1 portion \|` | lue |
| **Transposée** | les lignes sont des *versions* (« 0 % MG », « 3,2 % MG », « Entier »), les colonnes des métriques | `fromage-blanc.md` — trois versions dont les kcal vont du simple au double — n'était **pas chargée du tout**, en silence |
| **`\| Nutriment \| Valeur \|`** | la base (« pour 100 g ») est annoncée par le **titre de section**, pas par l'en-tête | **47 fiches sur 247** étaient absentes du calcul |

### 2. La base « pour 100 g » ne s'infère JAMAIS

Elle peut être annoncée hors du tableau (« ## Macros pour 100 g »). Quand aucune
mention explicite n'existe, un tableau à deux colonnes reste **ignoré** plutôt que
rapporté à une base supposée. Une macro rapportée à la mauvaise base est fausse
d'un facteur qu'aucun contrôle ne rattrape.

### 3. Une forme ne se choisit pas par défaut

Entre lentilles crues (339 kcal) et cuites (116), deviner c'est se tromper d'un
facteur 3 sans que rien ne le signale. Une fiche qui distingue des formes et dont
aucune n'est nommée par l'ingrédient rend `unresolved` avec son motif.

### 4. Seules les unités réellement convertibles convertissent

Pièce, gousse, tranche, botte, pincée dépendent d'un poids unitaire propre à
chaque aliment. Les convertir « à peu près » fabriquerait des macros fausses :
elles ressortent en `unresolved`.

La densité 1 est assumée pour les liquides aqueux. C'est faux pour l'huile (0,92)
et le miel (1,4), mais l'écart reste sous le bruit des fiches elles-mêmes.

### 5. L'appariement se fait par PRÉFIXE, pas par inclusion

Le nom de l'ingrédient doit **commencer** par la clé de la fiche : « chevre tres
sec » trouve « chevre », mais « chevre » ne prend pas « chevre chaud sur toast ».

### 6. Un ingrédient optionnel absent ne grève pas la couverture

Il ne compte pas non plus dans les macros : il est écarté des deux côtés. Le
compter en manque ferait baisser la couverture d'un plat complet.

### 7. Le produit acheté prime sur le générique, et s'efface devant la fiche vérifiée

Un produit scrapé d'un portail drive décrit le produit **exact** acheté, ce
qu'aucune fiche générique ne fait. Il prime donc sur le générique CIQUAL, et
s'efface devant une fiche `marques/` vérifiée à la main. Ordre : `marques/` >
`shopping_product.nutrition` > `generiques/`.

## Conséquences

- Ajouter une quatrième disposition suppose de **mesurer combien de fiches elle
  concerne** avant de l'écrire — le chiffre est la justification, pas l'intuition.
- Une fiche non lue doit ressortir dans `unresolved` avec son motif, jamais
  disparaître : `coverage` et `conclusive` priment sur le total (CLAUDE.md).
- Ces dispositions sont couvertes par les tests de `test_nutrition.py`. Une
  disposition qui n'a pas de test n'est pas supportée, quoi qu'en dise le code.
