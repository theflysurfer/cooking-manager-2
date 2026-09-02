# Corpus d'accommodations — ce que le foyer fait vraiment quand un plat ne convient pas

> **Ce document est une mesure, pas une doctrine.** Il annote des recettes réelles pour
> répondre à trois questions que la session du 2026-09-02 avait laissées ouvertes faute de
> corpus (`docs/rapports/2026.09.02_03.05_78c49e9`, refs #53).
>
> Mesuré le **2026-09-02** sur la base `cooking_manager` du VPS.
> Le périmètre se recompte : `SELECT family, count(*) FROM recipe GROUP BY family`.

## Méthode — la phrase-preuve est obligatoire

Une accommodation ne s'annote pas au jugé. Elle se lit sur **une phrase précise** de la
recette, citée verbatim ci-dessous. C'est la règle d'intake du vocabulaire
(`data/ontology/cooking-vocabulary.yaml`) : une bonne histoire n'est pas une preuve.

**Périmètre retenu** : les familles où un plat est servi à une tablée — `plat`, `salade`,
`salades-legumineuses`, `gratin`, `gratin-legume-appareil`, `bowl`, `sandwich`,
`wrap-sans-ble`, `cake-sale`, `petit-dejeuner`. Les familles écartées (`dessert-glace`,
`snack`, `patisserie`, `sauces-accompagnement`, `collation-proteinee`,
`petit-dej-proteine`) n'ont pas de convive à accommoder : personne ne prépare une part
séparée de sorbet.

## Les observations ancrées

| # | Recette | Technique | Convive | Phrase-preuve |
|---|---|---|---|---|
| 1 | `mafe-poulet` | `separate_portion` | Clémence | étape 7 — « Dans une petite poêle, saisir les crevettes 2-3 min de chaque côté. **Les ajouter dans la part de Clémence au service.** » |
| 2 | `mafe-poisson-legumes` | `full_substitution` | tous | ingrédient — « 1,2 kg **filet de cabillaud** (ou lieu noir) » là où `mafe-poulet` porte « 1,2 kg cuisses de poulet ». Étapes 1-5 **identiques mot pour mot** : c'est la même recette, protéine remplacée. |
| 3 | `salade-lentilles-froides-graines-courge` | `full_substitution` ×3 | Guillaume | frontmatter `applied_substitutions` — « ail → gingembre frais râpé (Guillaume) ; oignon blanc → oignon rouge (Guillaume) ; tomates séchées → retirées (Guillaume) », et l'ingrédient porte bien « 1 c.c. gingembre frais râpé ». |
| 4 | `tagliatelles-carbonara-vege` | `full_substitution` | tous | ingrédient — « 300 g **lardons végétariens** », et le titre l'annonce : « carbonara **végétariennes** ». |
| 5 | `salade-vietnamienne` | `self_service` | Léa | étape 5 — « Disposer le concombre à part **(libre-service pour Léa)** ». L'ingrédient le redit : « 1 kg concombre … (servi à part pour Léa) ». |
| 6 | `sandwiches-rillettes-thon` | `self_service` ×2 | Léa, Titouan | étape 4 — « Disposer câpres et cornichons **en libre-service** ». Ingrédients : « câpres, hachées (en libre-service pour Léa et Titouan) », « cornichons (en libre-service pour Léa) ». |
| 7 | `sandwiches-saumon-fume-saint-moret` | `self_service` | tous | étape 4 — « Concombres, câpres et cornichons **en libre-service pour que chacun se serve.** » |
| 8 | `tortilla-pizza-atelier` | `self_service` | tous | étape 3 — « **Laisser chacun garnir la sienne** : thon, poivron, champignons, mozzarella. » |

## Les contre-exemples — « à part » ne veut pas dire accommodation

Ils comptent autant que les observations : ils bornent la détection.

| Recette | Phrase | Pourquoi ce n'est PAS une accommodation |
|---|---|---|
| `berkoukes-crevettes-…` | étape 4 — « Sauter les crevettes 3 min **à part** » | technique de cuisson : les crevettes vont dans le plat de tout le monde |
| `mafe-poisson-legumes` | étape 7 — « Cuire le riz **à part** » | l'accompagnement se cuit toujours à part |
| `saumon-grille-…` | étape 4 — « poêlée **à côté** » | dressage |
| `gratin-courgettes-…-crevettes` | étape 5 — « sauter les crevettes 3 min … **les ajouter à la sortie du four** » | ajout tardif **pour tous** — la forme est celle d'une part séparée, l'intention non |

**Le marqueur fiable n'est donc pas « à part ».** C'est la présence, dans la même phrase,
d'un **nom de convive** (`person.name` en base) ou d'un marqueur collectif explicite
(« libre-service », « chacun se sert », « chacun garnit la sienne »).

`gratin-courgettes` est le cas piège : sans le marqueur, sa phrase est indiscernable de
l'étape 7 de `mafe-poulet`. C'est la preuve que la détection doit s'ancrer sur le convive,
jamais sur le verbe.

## Le partage réel — ce que le corpus tranche

| Technique | Observations | Statut vocabulaire avant | Ce que la mesure dit |
|---|---|---|---|
| `self_service` | **4** | **absente** | la plus pratiquée du foyer, et le vocabulaire ne la connaissait pas |
| `full_substitution` | 3 | probation | confirmée — dont 2 **matérialisées par une fiche jumelle**, pas par une règle |
| `separate_portion` | 1 | probation | confirmée, mais reste un cas unique |
| `separate_dish` | **0** | probation | **aucune observation** — déclarée sur une intuition, pas sur une pratique |

Trois enseignements que la seule recette `mafe-poulet` ne pouvait pas donner :

1. **Une technique manquait au vocabulaire.** Le libre-service n'est ni une substitution
   (le plat ne change pas) ni une part séparée (le cuisinier ne prépare rien de plus) :
   c'est le **convive** qui arbitre, pas la recette. C'est la voie la moins coûteuse, et
   c'est celle que le foyer emploie le plus.
2. **La substitution totale s'écrit en dupliquant la fiche.** `mafe-poulet` /
   `mafe-poisson-legumes` sont deux fiches pour un même plat. Le moteur propose une
   substitution *au moment de la compatibilité* ; le foyer, lui, l'a déjà figée dans une
   seconde recette. Une réparation devrait d'abord **chercher si la fiche jumelle existe**
   avant de recomposer une substitution.
3. **`separate_dish` n'est adossée à rien.** Elle reste en `probation` : la retirer serait
   prématuré (l'absence dans 28 recettes n'est pas une preuve d'impossibilité), mais lui
   donner le même poids qu'aux trois autres serait faux.

## Ce que ça tranche pour les trois limites du moteur (refs #53)

### Limite « étape de garniture qui pilote le plat » — résolue par le même marqueur

`mafe-poulet` étape 7 fait détecter *saisi* comme mode de cuisson du plat, alors que cette
étape est **précisément l'accommodation**. La règle tombe toute seule : **une étape porteuse
d'un marqueur d'accommodation est exclue du calcul du contexte du plat.** Une seule
détection sert les deux besoins.

### Limite « mijoté décrit sans le mot » — le corpus donne la conjonction

Aucune des deux fiches mafé ne contient « mijoter ». Ce qu'elles contiennent :

- `mafe-poulet` étape 4 — « Ajouter les patates douces et les aubergines. **Couvrir, cuire
  15 min** à feu moyen. »
- `mafe-poulet` étape 6 — « Poser les morceaux de poulet sur les légumes, **couvrir. Cuire
  12-15 min** jusqu'à ce que le poulet soit cuit à cœur. »
- `curry-coco-lieu-noir-lentilles-corail` étape 3 — « cuire **15 min à petits bouillons** »
- `curry-coco-…` étape 4 — « **couvrir, pocher 8 min** sans remuer »

**La conjonction à deux termes ne suffit pas — mesuré, pas supposé.** « milieu liquide +
durée » remonte 13 étapes sur le corpus, dont **8 faux positifs** : le couscous, le quinoa,
les pommes de terre, les vermicelles, les lentilles et les edamame cuisent tous « N min à
l'eau bouillante ». Un `à découvert` contient d'ailleurs `couvert` — la négation est
nécessaire.

**La conjonction à trois termes est exacte sur ce corpus.** Une étape qui, ensemble :

1. porte un verbe de cuisson en milieu liquide — `couvrir`/`couvert` (jamais précédé de
   `dé`), `mijoter`, `pocher`, `petits bouillons`, `frémissant` ;
2. porte une durée (`N min`, `N-M min`) ;
3. **nomme l'ingrédient protéique de la recette**.

Résultat mesuré le 2026-09-02 sur les 28 recettes : **3 étapes remontées, 3 vrais mijotés,
0 faux positif** — `mafe-poulet` 6, `mafe-poisson-legumes` 6, `curry-coco` 4. Et les
**21 étapes de contrôle** qui nomment une protéine sans la conjonction restent toutes
correctement hors mijoté : « saisir les pavés de saumon », « sauter les crevettes »,
« dresser avec le saumon en lanières », « égoutter le thon ».

C'est le troisième terme qui fait tout le travail. Le YAML avait raison d'écarter « couvrir »
seul ; la mesure montre que même « couvrir + durée » est insuffisant.

**Asymétrie assumée.** Le lexique du troisième terme est celui des `source` de règles —
donc uniquement des protéines carnées. `mafe-poisson-legumes` et `curry-coco`, qui mijotent
pourtant, ne sont pas détectés comme mijotés. C'est voulu : la détection ne sert qu'à
**choisir un substitut**, et dans une recette déjà pescétarienne il n'y a rien à substituer.
Si un jour le contexte sert à autre chose (affichage, filtre), cette asymétrie devra sauter.

### Limite « aucune cuisine ouest-africaine » — garder la clé, lui écrire ses synonymes

Deux recettes du vault sont ouest-africaines, et elles partagent un vocabulaire net :
**mafé**, **pâte d'arachide**, **huile d'arachide**, **patate douce**, riz en accompagnement,
« type sénégalais » dans le titre. C'est peu (2 sur 28) mais **ancré**, ce qui suffit à
sortir `west_african` de son état actuel — déclarée sans synonyme, donc indétectable.

Le motif de sa mise en probation (« aucune règle ne la cite ») reste vrai et devient la
tâche suivante : lui donner des synonymes la rend détectable, il faut alors qu'une règle la
consomme, sinon on produit un tag que rien ne lit.

## Ce qui manque encore — le gisement web

Ce document ne couvre que le **gisement (a)** du handoff : les recettes déjà dans le vault.
Elles mesurent la **pratique du foyer**, ce pour quoi elles sont le bon échantillon.

Elles ne peuvent pas mesurer autre chose : ce sont des fiches **déjà accommodées**. Une
recette qui pose un problème non résolu n'y figure pas — le foyer ne l'a pas retenue. Pour
éprouver le moteur sur des recettes *hostiles* (carnées, non adaptées, rédigées par
d'autres), il faut le **gisement (b)** : 30 recettes du web, premier livrable de
`deep-research#49`.
