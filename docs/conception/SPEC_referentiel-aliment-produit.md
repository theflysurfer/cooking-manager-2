---
title: Référentiel aliment & produit — sous-projet 1 de la refonte du garde-manger
axis: conception
proof_level: design-approuve
upstream: [USE_CASES_COURSES.md, ../decisions/0008-la-cle-d-appariement-du-garde-manger.md, ../decisions/0009-du-besoin-de-recette-a-la-quantite-d-achat.md]
downstream: [SPEC_garde-manger-journal.md]
status: approuvé en conception, non implémenté
date: 2026-09-07
issues: [69, 80, 82, 84]
---

# Référentiel aliment & produit

> Sous-projet **1 sur 5** de la refonte décidée le 2026-09-07. Il passe devant le
> garde-manger : sans identité réelle, un journal d'événements se recâble sur une
> chaîne de caractères.

## Le problème

Le système manipule deux choses sous un seul mot, et n'en connaît réellement
aucune.

| Identité | Ce que c'est | Où elle vit aujourd'hui | Combien |
|---|---|---|---|
| **Aliment** | du comté — ce qu'une recette consomme, ce dont on calcule les macros | `Coach Nutrition/aliments-vérifiés/generiques/` | 69 fiches |
| **Produit** | Comté Juraflore AOP au lait cru 250 g, `C1196689` — ce qu'on achète | `aliments-vérifiés/marques/` **et** `shopping_product` | 179 fiches + 49 lignes |

Ces référentiels s'ignorent. Trois conséquences mesurées le 2026-09-07 :

- **`pantry_item` n'a pas d'identité** (#69) : la clé est un nom normalisé qui ne
  pointe vers rien. 36 paires d'articles se ressemblent assez pour qu'un
  appariement puisse se tromper (« riz » / « vinaigre de riz »).
- **Une dose ne devient jamais un achat** (#80) : `purchase.py` sait dire « il te
  faut un conditionnement », pas lequel — le conditionnement est une propriété du
  produit, et personne ne la porte de façon requêtable.
- **Le choix produit se refait chaque semaine** (#82) : `shopping_product.item_requested`
  est du texte libre, sans clé vers l'aliment demandé.

Une quatrième conséquence, plus discrète : `nutrition.py` lit trois sources dans
un ordre de préférence (`marques/` > `shopping_product` > `generiques/`) **sans
qu'aucun lien n'existe dans l'autre sens**. Le garde-manger ne sait pas quel
aliment il contient, donc le stock ne peut rien dire des macros.

## Périmètre

**Dans** : les tables `food` et `product`, leur relation, la chaîne d'entrée d'un
nom, la migration des 248 fiches, la bascule de `nutrition.py` sur la DB, les
outils MCP de lecture et d'écriture du référentiel.

**Dehors** : le journal du garde-manger (sous-projet 2), les recettes (3), les
menus (4), `Convives.md` (5). Le panier Auchan et la mémoire d'achat (#82)
consomment ce référentiel mais ne sont pas livrés ici.

## Le modèle

### `food` — l'aliment

Dérivé des 69 fiches `generiques/`, dont les champs existent déjà :

| Colonne | Source | Note |
|---|---|---|
| `key` | `slug` | l'identité stable — c'est elle que vise un alias (ADR 0008) |
| `name` | `title` | |
| `category` | `categorie` | axe fermé → candidat ontologie |
| `kind` | `type_produit` | |
| `ciqual_code` | `ciqual_code` | |
| `macros_per_100g` | tableau « Macros pour 100 g » | JSONB |
| `conservation` | déduit du rayon aujourd'hui, déclaré demain | périssable / stable |
| `source`, `verified_at` | `source_macros`, `date_maj` | |

### `food_unit` — les unités d'usage d'un aliment

Un aliment se mesure de **plusieurs** façons, et le gramme n'est que l'une
d'elles : sur 449 lignes d'ingrédients, il ne pèse que **38 %** (170) — devant
`pièce` (114), `c.s.` (65), `c.c.` (37), `gousse` (13), `pincée`, `botte`,
`scoop`, `tranche`.

```
food_unit(food_key, unit, grams, source)
   oeuf   · pièce  · 60 · fiche
   ail    · gousse ·  5 · fiche
   persil · botte  · 30 · observation
   whey   · scoop  · 30 · étiquette
```

Plusieurs lignes par aliment, alimentées par les sections « Par X (~N g) » des
fiches. C'est ce que #80 attend pour convertir une pièce — pas une colonne
unique, qui supposerait qu'un aliment n'a qu'une unité d'usage.

> **L'unité d'usage est conservée partout** — stockée, affichée, déclarée. La
> conversion est un **recours**, jamais un pivot : pour comparer un besoin à un
> stock, ou pour calculer des macros. Quand elle n'existe pas, on ne convertit
> pas : `inconnu` ou `non_resolu`, jamais un chiffre fabriqué. Une recette dit
> « 2 gousses d'ail » et l'affiche ainsi, même si la macro a eu besoin de 10 g.

### `product` — ce qui s'achète

Dérivé des 179 fiches `marques/` **et** des lignes `shopping_product` :

| Colonne | Note |
|---|---|
| `food_key` | → `food.key`. **Un produit appartient à un aliment**, jamais l'inverse |
| `name`, `brand` | |
| `ean` | la clé stable inter-magasins (le C-code ne l'est pas) |
| `store`, `store_ref` | un produit existe dans une enseigne |
| `pack_count`, `pack_size_value`, `pack_size_unit` | **le conditionnement** — `x12`, `250 g`, `sachet 750 g` |
| `nutriscore`, `macros_per_100g` | quand la fiche ou le drive les donne |
| `last_seen_price`, `price_per_kg` | mesures datées, jamais des constantes |

⚠️ **Le conditionnement sort du nom.** Le slug `auchan-bio-plein-air-oeufs-x12`
porte `x12` dans son identité, comme le ticket portait `Oeufs plein air x10` :
c'est ce qui a créé un doublon d'aliment le 2026-08-19. `x12` devient
`pack_count = 12`, et le nom redevient un nom.

⚠️ **Une contrainte de personne n'est pas une propriété d'aliment.** La fiche des
œufs porte « Léa : pas d'œufs durs/pochés/plat/mollet/omelette ». Cette phrase
appartient à `person.dislikes`, seul endroit que `/compatibility` lit. Migrer la
fiche sans déplacer cette ligne la rendrait invisible.

## L'entrée d'un nom

Aucun libellé n'entre tel quel. Quatre étages, on s'arrête au premier qui tranche.

| Étage | Ce qu'il fait | Déterministe |
|---|---|---|
| 1. Normalisation | découpe, pluriel, parenthèses ; le conditionnement part vers `pack_*` | oui, testé |
| 2. Alias connu | `pantry_alias` — une décision prise ne se redemande jamais | oui |
| 3. Appariement | inclusion de mots porteurs, mots-outils et marque ignorés | oui, testé |
| 4. Vérification sémantique | propose un rapprochement, **ne l'applique pas** | non |

L'étage 4 compare quatre signaux, qui n'ont pas le même pouvoir :

| Signal | Pouvoir |
|---|---|
| Nom | **suggère** — jamais concluant seul |
| Poids / conditionnement | **réfute** : un pot de 10 g et un sachet de 500 g ne sont pas le même usage |
| Prix au kilo | **réfute** : un ordre de grandeur d'écart (safran contre curcuma) — le signal le plus dur à tromper |
| Marque | ne réfute jamais l'**aliment**, décide du **produit** |

> **Un signal peut réfuter seul ; aucun ne peut conclure seul.** Un rapprochement
> ne se propose que si le nom concorde et qu'aucun autre ne le réfute.

Ce que Julien tranche **devient un alias** : la question ne revient pas.

⚠️ `price` vaut `0.0` dans les résultats de recherche Auchan — un parsing manqué,
pas un prix (mcp-vps#178). Un prix absent **ne réfute ni ne confirme** : il rend
le critère muet et fait descendre la confiance d'un cran, il ne l'augmente pas.

### Le ticket de magasin passe par le catalogue

`PILONS POULET PF 4,35 €` n'a ni nom propre ni quantité. `grocery_search` sur le
libellé rend des candidats ; Julien valide ; on récupère **nom, conditionnement
et EAN d'un coup**, et le produit entre dans le référentiel.

Deux dégradations propres, parce que ce chemin échoue souvent :

- **catalogue injoignable** (la session Auchan était morte ce soir-là) → le
  produit entre avec son libellé de ticket et le marqueur `à rapprocher` ;
- **aucun candidat convaincant** → même marqueur. Un produit de boucherie ou de
  marché n'existe pas au drive, ce n'est pas une anomalie.

Jamais un chiffre déduit d'un prix, jamais un rapprochement sans catalogue.

## Ce que devient `nutrition.py`

Ses trois sources deviennent deux tables et une règle de préférence, inchangée
dans son esprit : **produit précis > produit générique de la même enseigne >
aliment CIQUAL**. Ce qui change :

- il lit la DB, plus les fichiers ; `load_food_base_cached()` disparaît ;
- un aliment absent reste `unresolved` **avec son motif** — la doctrine « pas
  d'hypothèse » ne bouge pas ;
- `coverage` et `conclusive` priment toujours sur le total.

## Les outils MCP

| Outil | Rôle |
|---|---|
| `food_search(query)` | trouver un aliment |
| `food_detail(key)` | macros, poids unitaire, produits rattachés |
| `food_upsert(...)` | créer ou corriger un aliment |
| `product_upsert(...)` | créer ou corriger un produit, rattaché à un aliment |
| `product_link(ean \| store_ref, food_key)` | trancher un rapprochement — écrit l'alias |

`pantry_add`, `pantry_update` et `pantry_remove` sont **décommissionnés** avec le
sous-projet 2, pas maquillés en façades : un écrivain qui ne respecte pas la
grammaire de quantité fait diverger le stock en silence.

## Migration

Cinq étapes, dans cet ordre, et l'ordre n'est pas négociable.

1. **Importer** les 248 fiches, sans rien supprimer. Les deux mondes coexistent.
2. **Comparer** — un rapport prouve l'équivalence fiche par fiche : macros,
   poids unitaire, conditionnement extrait, contraintes de personne déplacées.
   **Un écart non expliqué bloque l'étape 3.**
3. **Basculer les écrivains** — outils MCP, ingestion des tickets et du drive.
   Le vault devient muet, reste en place.
4. **Observer une semaine réelle** — un menu, des courses, des déclarations.
5. **Archiver** les fiches (`aliments-vérifiés/_archive/<date>/`) et **retirer le
   code de lecture** correspondant.

La base legacy `logs/aliments/` (~80 fiches, « migration progressive » depuis
juillet) est traitée ici : résorbée dans `food`, ou déclarée morte. Elle ne
reste pas « en cours ».

⚠️ L'étape 5 fait partie de la livraison. Un décommissionnement dont personne ne
retire le code laisse deux chemins d'écriture vivants.

## Critères de succès

1. Chaque ligne de `pantry_item` pointe une `food.key` existante, ou porte
   `à rapprocher` — **aucun état intermédiaire silencieux**.
2. `purchase.py` convertit une pièce en grammes quand `food.unit_weight_g`
   existe, et continue de rendre `non_resolu` sinon.
3. Les macros d'un menu déjà calculé sont **identiques** avant et après bascule,
   ou l'écart est expliqué ligne à ligne.
4. Un ticket de magasin produit des produits rattachés à un aliment, ou marqués
   `à rapprocher` — jamais de doublon d'aliment créé par un conditionnement.
5. Les tests couvrent, un par piège : conditionnement dans le nom, réfutation par
   le poids, réfutation par le prix, prix à `0.0` (muet, pas favorable), marque
   différente (même aliment), contrainte de personne déplacée.

## Écarté

- **Mettre aliments et produits dans l'ontologie.** Ce sont des ensembles
  ouverts ; une ontologie porte des axes fermés. Y entrent en revanche quatre
  axes déjà dérivés (voir ci-dessous).
- **Faire du gramme le pivot.** Il ne couvre que 38 % des lignes ; convertir
  d'office effacerait l'unité dans laquelle la cuisine se pense.
- **Laisser `nutrition.py` lire le vault** après la bascule. Deux sources de
  macros divergent sans alerte : c'est le défaut qu'on corrige, pas un compromis.
- **Rapprocher automatiquement sur le nom seul.** Un faux rapprochement fait
  sauter un achat, et ça ne se découvre qu'en cuisine.

## L'axe `units` doit entrer dans l'ontologie

Mesuré le 2026-09-07 : **cinq tables d'unités, dans quatre fichiers**, avec des
découpages qui ne se recouvrent pas — `UNIT_ALIASES` (orthographes),
`_TO_BASE` (familles), `_SPOON_SCALE` (doses), `GRAMS_PER_UNIT` (facteurs vers le
gramme), `MEASURED/COUNTABLE/DOSE_UNITS` (rôles d'achat). Preuve que l'axe a
dérivé sans gouvernance : `scoop`, employé 4 fois, n'appartient à aucune des
trois dernières listes — il sort `non_resolu` sans que personne ne l'ait décidé.

Chaque unité porte : `aliases` · `family` (masse · volume · dénombrable · dose) ·
`role` (mesurable · comptable · dose) · `universal_factor` quand il vaut partout
(1 c.s. = 15 ml, indépendant de l'aliment). Les cinq tables deviennent des vues
sur cet axe.

Ce qui n'y entre pas : les équivalences **propres à un aliment** — elles vivent
dans `food_unit`.

Trois autres axes sont dans le même état et se reprennent avec lui, au
sous-projet 2 : les **types d'événement**, les **niveaux** (aujourd'hui
`XSTATUS_MAP`, enrichi au fil du vault avec `urgent`, `a-jeter`, `perime`,
`vérifier-dlc`), et la **classe de conservation des rayons** (aujourd'hui déduite
par sous-chaîne du libellé : renommer un rayon désarme la péremption en silence).

⚠️ Le générateur d'`ontology-manager` a un **jeu de champs fixe** : un champ
ajouté au YAML n'atteint pas l'artefact et le consommateur lit une valeur vide
sans erreur. Chaque nouvel attribut = les deux dépôts **plus un test** qui prouve
qu'il survit à la génération.

## Suites

| # | Sous-projet |
|---|---|
| 2 | **Le garde-manger** — journal d'événements, niveaux, revue de rayon, fraîcheur par article (#84) |
| 3 | **Les recettes** — 73 fiches en DB, ingrédients pointant `food` |
| 4 | **Les menus** — en DB, fin de `POST /api/ingest` |
| 5 | **`Convives.md`** — suppression, `person` fait déjà autorité |
