# 0012 — Les partis pris du front, et leurs raisons

- **Statut** : accepté
- **Date** : 2026-09-08
- **Porte** : `web/app.js`, `web/style.css`
- **Issues** : #71

## Contexte

Le front portait ses justifications en commentaires — quarante blocs dans
`app.js`, cinquante-neuf dans `style.css`. Rien ne les exécutait, donc rien ne les
vérifiait : chacun faisait autorité jusqu'à devenir faux en silence.

Le retrait de cette prose (#71) ne devait pas emporter le raisonnement. Ce qui
suit est ce qui méritait de survivre. Trois familles ont été écartées d'emblée :
les séparateurs de section, les rappels de contraintes iOS 12 — déjà portés par le
CLAUDE.md et **vérifiés** par `audit_ios12.py` et eslint — et les redites de
règles métier déjà écrites ailleurs (`outcome: inconnu`, notamment).

## Décision

### 1. La photo mène, et son absence ne casse pas la grille

Treize pour cent du catalogue seulement porte une photo. Une carte sans image
n'affiche donc pas un cadre vide : un aplat et un titre, qui tiennent le même
rectangle. La grille reste régulière, et l'œil ne lit pas l'absence de photo comme
une erreur de chargement.

### 2. « Aujourd'hui » saute aux yeux à distance

L'app se consulte en cuisine, l'iPad posé à un mètre. Le repas du jour est traité
comme le seul moment d'usage réel : tout le reste de la semaine est du contexte.
C'est ce qui justifie l'écart de traitement visuel entre la ligne du jour et les
autres.

### 3. La puce « Cette semaine » relie le catalogue au menu

Sans elle, les recettes du catalogue se valent toutes et rien ne dit lesquelles
sont au programme. Ce n'est pas un filtre parmi d'autres : c'est le seul lien
entre les deux vues, ce qui justifie qu'elle ne se comporte pas comme les autres
puces.

### 4. Les gestes ne s'affichent que là où ils ont un sens

Sur une ligne de courses, les quatre gestes du garde-manger ne sont pas tous
proposés : demander « tu en as ? » pour un ingrédient qu'on sait manquant fabrique
une question sans réponse utile. Le geste suit l'état de la ligne.

### 5. L'âge de l'inventaire est une donnée de premier plan

Il décide si le frais est encore crédible. L'afficher en note de bas de page
revenait à le rendre invisible au moment exact où il compte — juste avant de
décider qu'on a ce qu'il faut.

### 6. Les restes ne sont pas un manque

Un repas de restes n'a pas de fiche, par conception (#76). L'afficher dans la même
bannière que les repas sans recette ferait clignoter une alerte qu'on ne peut pas
éteindre, et une alerte permanente ne s'éteint pas : elle se cesse d'être lue.

### 7. L'import d'une page de livre se relit, toujours

La capture passe par `<input type="file" capture>`, pas `getUserMedia` — même
famille de limite que MediaRecorder, qui avait déjà imposé de masquer le micro sur
l'iPad mini 2.

L'écran de relecture est le cœur de la fonctionnalité, pas une politesse : un
modèle vision **hallucine des quantités plausibles**, et la page photographiée
n'est plus consultable une fois le livre rangé. Toute ligne non comprise doit se
voir plutôt que disparaître.

### 8. Le mouvement sert la lecture ou n'existe pas

L'A7 de l'iPad mini 2 date de 2013 : `opacity` et `transform` uniquement, sous
300 ms, jamais `ease-in`. Le survol n'est appliqué qu'aux vrais pointeurs — au
tactile, un `:hover` reste collé après le doigt.

## Conséquences

- Le POURQUOI du front a un foyer unique et durable ; le code n'en porte plus.
- Les **pièges de mise en œuvre** (ce qui casse si on refactorise sans savoir)
  ne sont pas ici : ils vont dans `julien-audit-ios12-compat`, où un gate peut
  les vérifier. Un ADR explique un choix ; il ne garde pas une main.
- Un parti pris qui change ne se corrige pas ici : il supersède cet ADR.
