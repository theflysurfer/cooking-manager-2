# 0011 — Un import ne tranche pas, il déclare

- **Statut** : accepté
- **Date** : 2026-09-07
- **Porte** : `backend/food_import.py`, `cooking_manager/matching.py`
- **Issues** : #69, #82, #85 · ontology-manager#13
- **Suit** : [0010](0010-le-vault-cuisine-est-decommissionne-la-db-fait-foi.md)

## Contexte

La phase 1 du référentiel aliment fait entrer 248 fiches du vault dans les tables
`food`, `food_unit` et `product`. Le plan d'exécution
(`docs/conception/PLAN_referentiel-aliment-produit-phase1.md`) portait le code de
chaque module ; quatre points ont dû être tranchés autrement, tous mesurés à
l'exécution, tous de la même famille : **une ambiguïté résolue en silence produit
un résultat crédible et faux**.

Aucun ne produisait d'erreur. Trois n'ont été visibles que parce qu'un chiffre
attendu ne tombait pas.

## Décision

### 1. Une clé revendiquée par deux fiches n'est pas importée

`generiques/feculents/pain-complet.md` (247 kcal) et
`generiques/feculents-legumineuses/pain-complet.md` (235 kcal) normalisent vers
la même clé. L'upsert gardait la dernière lue — un arbitrage entre deux sources
CIQUAL, rendu par l'ordre de parcours du disque.

Les deux fiches sortent de l'import et entrent dans `collisions`, nommées avec
leurs kcal. **Fusionner ou renommer est un choix humain.** Le symptôme initial
était un écart d'une unité : 62 aliments écrits, 61 en base.

### 2. Une fiche à plusieurs formes sans forme neutre n'est pas résolue

`lentilles.md` porte « Crues » et « Cuites » (339 kcal contre 116). Prendre la
première donnait un facteur 3. Sans forme neutre `100g`, la fiche part en
`skipped` **avec son motif** — 16 fiches sur 248, chacune nommée.

### 3. Le dossier prime sur le frontmatter

49 fiches de `generiques/` portent `marque: null`. Le frontmatter est lu ligne à
ligne, donc la **chaîne** `"null"` est vraie : 51 aliments génériques devenaient
des produits de marque, et l'import rendait 18 `food` au lieu de 62.

`generiques/` et `marques/` tranchent ; un champ `marque` ne décide que hors des
deux, et une valeur textuelle `null` / `none` / `-` / `à compléter` n'est pas une
marque. La cause amont — un frontmatter typé par un parseur YAML — est #85.

### 4. Un signal absent et un signal faux ne se traitent pas pareil

Dans `matching.py`, un prix **absent** (`None`) est neutre : il ne rapproche ni
ne réfute. Un prix **à 0.00 €** est présent et impossible — c'est un parsing
manqué des résultats Auchan. Il rend le verdict `unsure` et **se déclare dans les
motifs**. Les confondre rendait tout rapprochement incertain, y compris entre
deux fiches qui n'ont simplement pas de prix.

Même logique sur les noms : le nom le plus court doit **ouvrir** le plus long.
« origan » ouvre « origan séché » (un qualifiant s'ajoute en queue) ; « riz »
n'ouvre pas « vinaigre de riz », dont le mot de tête nomme un autre aliment. Un
simple test d'inclusion rapprochait les deux.

## Conséquences

- Le rapport d'équivalence (`GET /api/food/report`) porte `missing`,
  `macro_mismatch`, `collisions`, `unlinked_products`, `person_constraints` et
  `skipped`. **Aucun consommateur ne bascule tant que les trois premiers ne sont
  pas vides.**
- Un aliment en collision est **absent de la base** : un consommateur qui le
  cherchera ne le trouvera pas, plutôt que d'en lire une version tirée au sort.
  C'est le bon côté de l'erreur.
- `person_constraints` est une liste de **candidats**, pas un verdict : une
  contrainte demande un marqueur d'aversion, pas seulement un prénom suivi de
  « : ». Sans ce filtre, la liste rendait 86 lignes dont l'essentiel était du
  dosage (« Utilisation Julien : 40 g = 6.8 g glucides ») — illisible, donc
  inexploitable.

## Ce que la décision coûte

Un import qui refuse de trancher **ne finit jamais tout seul** : chaque
collision, chaque fiche écartée demande une main humaine avant la phase 2. Le
prix est assumé — l'alternative était 51 aliments mal classés que rien
n'annonçait.
