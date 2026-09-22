---
numero: 0032
titre: Un achat et un ingrédient ne se rapprochent que par un aliment
statut: accepté
date: 2026-09-22
concerne:
  - backend/db.py
  - backend/app.py
  - cooking_manager/matching.py
  - cooking_manager/pantry.py
---

# 0032 — Un achat et un ingrédient ne se rapprochent que par un aliment

## Contexte

Le menu `2026-09-21_semaine-aubagne-enfants` a été composé le 20/09. La commande `1f900f71` du
même jour portait 46 lignes ; 41 sont entrées au garde-manger le 21/09 — cinq se sont perdues entre
la commande et le stock. Julien a constaté le lendemain des achats qu'aucune recette du menu ne
consomme.

Confrontation des 41 lignes aux 104 ingrédients distincts du menu, le 2026-09-22 :

- **12** tombent exactement sur un ingrédient.
- **14** désignent le même aliment sans jamais s'apparier. `auchan pois chiche 530g` contre
  `pois chiche` · `steak hache de boeuf 15 mg` contre `boeuf hache` · `auchan crevette nordique
  decortiquee cuite 200g` contre `crevette decortiquee` · `auchan champignon de paris pied et
  morceau 800g` contre `champignon de paris`. Un cas ne cède à aucune règle de chaîne :
  `quaker cruesli cereale au chocolat noir 900g` contre la clé récurrente `céréales petit-déjeuner`,
  **zéro mot en commun**.
- **15** sont de vrais achats sans besoin déclaré.

La cause est mécanique. `cooking_manager/matching.py:108` exige que le nom le plus court **ouvre**
le plus long : `auchan crevette nordique…` ne commence pas par `crevette`, donc `REFUSE`.
`cooking_manager/pantry.py:108` rend `None` par le même chemin. Ni l'un ni l'autre ne lève quoi que
ce soit : le résultat d'un appariement manqué est indiscernable d'un produit absent, et la liste de
courses fait racheter.

Le référentiel nécessaire existe pourtant. La table `food` porte 192 aliments et `food_form` 205
formes, sans un seul aliment dépourvu de forme. Mais **personne ne la joint sur ce chemin** : ni
`pantry_item` ni `recipe_ingredient` ne la référencent, et `product` compte 130 lignes sans
`food_key` sur 170. Les 330 lignes de `pantry_item` n'ont jamais rempli leur colonne
`shopping_product_id`. Tout se rapproche par chaîne française, entre un libellé commercial et un
libellé de recette.

Aucune route ne va du stock vers les recettes. Les quelque 110 routes de `backend/app.py` vont
toutes du menu vers la liste de courses ; `GET /api/menus/{slug}/shopping-list` lit bien le
garde-manger, mais après que le menu soit figé.

## Décision

**L'aliment est la seule clé d'appariement.** Un achat, une ligne de stock et un ingrédient de
recette ne se rapprochent qu'en désignant le même `food.key`.

1. `pantry_item.food_key` et `recipe_ingredient.food_key` deviennent des colonnes, référençant
   `food(key)`. Cette dernière n'est possible qu'après l'ADR 0031, qui donne la table à CM2.
2. Un rapprochement se décide par une chaîne, et son échec s'écrit : exact sur `name_normalized`,
   puis `pg_trgm` au-dessus de 0,45, puis Claude via l'API HTTP Ollama sur ce qui reste ambigu. Un
   doute rend `food_key NULL`, qui se compte et s'affiche. Rien ne s'invente.
3. **L'arbitrage précède l'entrée.** `POST /api/shopping/validate-cart` rend `ok: false` tant
   qu'une ligne du panier n'est pas tranchée, et nomme celles qui manquent.
4. Un arbitrage rendu s'écrit dans `pantry_alias` et ne se redemande jamais.
5. Une forme est le défaut, un aliment neuf est une décision. `pave de saumon` devient
   `food_form(food_key='saumon', label='pavé')` sauf scission explicite, tracée.
6. Une même file, deux portes : `GET /api/pantry/pending-links` sert Claude Code pendant la course
   et l'interface web à tête reposée. Ce qui est tranché d'un côté disparaît de l'autre.
7. Le ménager et le non-alimentaire restent hors du référentiel. Ils se déclarent `recurrent` dans
   `shopping_preference` et ne comptent pas comme un trou de rattachement.
8. `GET /api/pantry/cookable` rend ce que le stock permet : ce qu'on a, les recettes que ça couvre,
   et ce qu'aucune recette du référentiel ne sait consommer.
9. `shopping_session.status` prend `cart`, `ordered` ou `abandoned`, en extension du gate de
   l'ADR 0028.

Le rattrapage se fait en une passe, groupé par aliment : les libellés qui désignent la même chose
arrivent ensemble, ce qui ramène 460 lignes à environ 80 décisions.

Le critère de réparation est un test bloquant. `tests/test_ratchet_rattachement.py` rejoue les
41 libellés réels du 2026-09-21 ; chacun doit finir rattaché, déclaré hors menu, ou nommé en
attente d'arbitrage. **Aucun ne doit finir en silence.** Douze seulement y parviennent aujourd'hui.

## Conséquences

- Une commande franchit désormais trois portes : arbitrage complet, `persist-cart` réussi (ADR
  0028), puis diff de réconciliation accepté. La commande n'est plus un geste d'un seul tenant, et
  c'est le coût assumé de savoir ce qu'on achète.
- Un achat non rattaché **bloque**. C'est volontaire : le 21/09, 41 lignes sont entrées sans qu'une
  seule soit rattachée, sans blocage et sans trace.
- Le rattrapage initial coûte une session dédiée avant que `cookable` rende autre chose qu'une
  liste vide — laquelle se lirait « je n'ai rien » au lieu de « je n'ai rien su rattacher ».
- Claude entre dans un chemin de décision. Sa sortie est bornée : un candidat du référentiel, ou
  `NULL`. Il ne crée jamais un aliment.
- `pantry_item` reste un journal d'entrées (#94, #118) : cet ADR lui donne une identité, pas un
  décompte. Les déductions de consommation se proposent et ne s'appliquent pas seules.
- Le rayon sec repose sur une revue trimestrielle et un rappel. **Une revue sautée laisse le stock
  se lire comme vrai**, et rien d'autre que le rappel ne le dit. Julien a choisi ce risque en
  connaissance de cause, contre une péremption qui aurait rendu ces lignes « inconnues » d'office.

## Alternatives écartées

- **Durcir `normalize_name` et garder les chaînes** : zéro migration, mais l'appariement reste un
  pari sur le français et son échec ne lève rien. `brocoli` contre `brocolis en fleurette` rend
  déjà `None` sur une frontière de mot, et `cruesli` contre `céréales petit-déjeuner` n'a aucune
  solution lexicale.
- **Étendre `pantry_alias` sans colonne d'aliment** : l'infrastructure existe, mais un alias
  manquant reste invisible — aucun compteur ne le voit. C'est la même panne, déplacée d'un cran.
- **Table de liaison `ingredient_food`** : nécessaire tant que `recipe_ingredient` appartient à un
  autre dépôt, inutile après l'ADR 0031, et productrice de lignes orphelines.
- **Ne rattacher que les achats et le stock** : laisse le besoin en chaîne, donc laisse intacte la
  moitié de la panne du 21/09.
- **Signaler au lieu de bloquer** : c'est exactement ce qui s'est passé le 21/09, sans même le
  signalement.
- **Une péremption par rayon pour le sec** : rendrait `inconnu` toute ligne non revue depuis 90
  jours — plus sûr, écarté par Julien au profit du rappel.
- **Embeddings locaux sur CPU** : déterministes et hors ligne, mais ils apportent un seuil de
  similarité sans apporter de jugement ; le cas `cruesli` reste hors de portée.
- **Jev (TypeSafe AI)** : rendrait une confiance calibrée, donc un seuil honnête sous lequel écrire
  `NULL`. Écarté aujourd'hui — liste d'attente, API hébergée, poids non publiés, et un plafond de
  255 options qui impose de toute façon le pré-filtre des étapes 1 et 2. À réévaluer comme arbitre
  de l'étape 3 quand l'accès s'ouvrira.
