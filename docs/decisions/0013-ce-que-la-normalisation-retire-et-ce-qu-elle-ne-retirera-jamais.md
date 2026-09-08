# 0013 — Ce que la normalisation retire, et ce qu'elle ne retirera jamais

- **Statut** : accepté
- **Date** : 2026-09-08
- **Porte** : `cooking_manager/ingredients.py`, `convives.py`, `nutrition.py`, `normalizer.py`
- **Issues** : #71
- **Supersède partiellement** : rien — cet ADR consigne des règles qui vivaient en commentaires

## Contexte

Apparier un ingrédient de recette, un terme de contrainte et un article du
garde-manger suppose de réduire chacun à une forme comparable. Chaque règle de
réduction a été écrite **après un appariement raté**, jamais par principe. Elles
vivaient en commentaires : rien ne les exécutait, donc rien ne les vérifiait.

## Décision

### 1. Les ligatures s'expansent AVANT tout repli ASCII

`œ` et `æ` n'ont **aucune décomposition Unicode** — ni canonique, ni de
compatibilité. `NFKD` les laisse intactes, et `encode('ascii', 'ignore')` les
**supprime** : « œuf » devenait « uf », « bœuf » devenait « buf ».

Conséquence mesurée : un terme « oeuf dur » ne rencontrait jamais un plat écrit
« œuf dur », et la salade niçoise passait le contrôle devant Léa et Clémence, qui
refusent l'œuf dur. Le français culinaire en est plein — œuf, bœuf, cœur.

### 2. On retire des mots-outils, jamais des qualificatifs

« huile d'olive » et « huile olive » désignent le même produit ; leurs clés
diffèrent parce que l'une vient d'un nom de fichier et l'autre d'une phrase. Les
particules (`de`, `du`, `à`, `en`) se retirent donc.

⛔ **Un qualificatif ne se retire jamais.** « fraîche », « entier », « liquide »,
« surgelé », « fumé » changent l'identité : crème fraîche ≠ crème, lait entier ≠
lait demi-écrémé, abricots congelés ≠ abricots frais.

Le raisonnement qui tranche : **sur-normaliser est le mauvais côté de l'erreur**.
Un faux positif fait sauter un achat nécessaire, et cela ne se découvre qu'en
cuisine, le soir, sans recours. Un `inconnu` posé en question se règle en une
seconde.

### 3. Les termes se comparent en mots entiers, et la table doit être complète

« lard » manquait alors que « lardon » était présent. Comme la comparaison porte
sur des mots entiers, « 8 tranches de lard fumé » ne rencontrait aucune entrée :
deux recettes du livre de fromages passaient pour compatibles pescétarien.

La table des familles exclues par régime est **volontairement large** : mieux vaut
une alerte à lever qu'un plat servi à quelqu'un qui ne peut pas le manger.

### 4. `(?!\w)` et surtout pas `\b` après une unité

Les unités qui finissent par un point — `c.c.`, `c.s.`, `q.s.` — ne peuvent
**jamais** satisfaire `\b` : le point et l'espace qui suit sont tous deux non
alphanumériques, il n'y a donc aucune frontière de mot entre eux. Avec `\b`,
« 1 c.c. extrait de vanille » ressortait en unité « pièce » et nom « c.c. extrait
de vanille ».

### 5. Le vault écrit en typographie, pas en ASCII

Les quantités arrivent en « ½ oignon », « ¼ de citron » — invisibles d'une regex
numérique. Les fourchettes mélangent tiret, demi-cadratin et cadratin dans le même
corpus. Les trois formes doivent être acceptées.

### 6. Une section peut être numérotée

Une fiche rédigée en plan numéroté (« ## 3. Ingrédients (4 pers) ») porte les
mêmes listes que les autres. Sans tolérance du préfixe, elle ressortait
**intégralement vide** — ingrédients et étapes.

Un paragraphe en gras clôt une liste : c'est une note (« **Variantes testées** :
… »), pas un ingrédient.

### 7. Un tableau markdown ne se balaie pas en entier

`Convives.md` porte plusieurs tableaux — aversions partagées, rythme hebdomadaire,
substituts de saveurs. Les balayer tous faisait entrer « Maïs », « Mardi »,
« Mercredi » dans le répertoire des convives, avec des « interdits » absurdes.
L'extraction se borne à sa section.

### 8. PyYAML rend un objet là où on attend une chaîne

`date: 2026-08-04` devient un `datetime.date` sans qu'on le demande. Le bloc
`meals` part ensuite en JSONB via `json.dumps`, qui ne sait pas le sérialiser →
500 à l'ingestion. La conversion en ISO se fait **une fois**, à la normalisation,
plutôt que d'être rattrapée chez chaque consommateur.

## Conséquences

- Toute nouvelle règle de normalisation s'ajoute **sur observation d'un
  appariement raté**, jamais par symétrie ou par principe.
- Une règle ajoutée ici change les clés déjà stockées :
  `POST /api/pantry/renormalize?dry_run=true` avant, sans `dry_run` ensuite
  (ADR 0008).
- Les cas nommés ci-dessus sont couverts par des tests : c'est là qu'ils sont
  vérifiés, et non dans un commentaire qui peut devenir faux sans erreur.
