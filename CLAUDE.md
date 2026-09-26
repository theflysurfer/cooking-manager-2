# Cooking Manager 2

App web de cuisine familiale : recettes, menus de la semaine,
courses différentielles, macros. **Cible : iPad mini 2 / Safari 12.5.8**, en cuisine.

<!-- fast-search-directive -->
⚡ Dépôt sous Dropbox : chercher avec les outils **Grep** / **Glob** / **Read**, jamais
`grep`/`find` en bash (100 à 4000× plus lents). Bash reste bon pour git, ssh, curl, pytest.
<!-- /fast-search-directive -->

## Commandes

```bash
ssh srv759970 'cd /opt/cooking-manager-2 && git pull && .venv/bin/pip install -q . && sudo systemctl restart cooking-manager'
ssh srv759970 'curl -s localhost:8795/api/<route>'   # basic auth nginx : toujours via le VPS
ssh srv759970 'curl -s -X POST localhost:8795/api/ingest'   # re-link des repas du menu
ssh srv759970 'docker exec postgresql-shared psql -U cooking -d cooking_manager -c "SELECT ..."'
```

## Gates avant commit — tous bloquants

```bash
python -m ruff check cooking_manager/ backend/ tests/
python -m pyright
python -m pytest tests/
python ~/.claude/skills/julien-audit-comments/check_comments.py . --ci
python ~/.claude/skills/julien-audit-ios12-compat/scripts/audit_ios12.py web   # si web/ touché
# pytest -m e2e frappe l'API réelle et ÉCRIT EN PRODUCTION : opt-in, jamais par défaut
```

## Architecture

`cooking_manager/` = domaine pur, **sans I/O réseau** (un module qui en fait est mal rangé).
`backend/` = FastAPI, schéma, writers DB, `stt.py`, `cooking_mcp.py`. `web/` = statique, zéro
build. `data/ontology/` = source du vocabulaire.
`backend/url_parser/`, `images.py`, `book_import.py` = parsing web, import de livre et
**génération d'image**, absorbés de recipe-manager (ADR 0031) : son service 8796 est arrêté et
**désactivé**, ⛔ ne jamais le relancer — tout passe par 8795. Déploiement : systemd
`cooking-manager` (8795) + `cooking-mcp` (3868) sur srv759970 ; CM2 est **propriétaire** des
tables recette. Waaker appelle `POST /api/recipes/parse-html` sur 8795.
La route photo refuse une fiche qui a déjà un `photo_url` (`generated: false` + `reason`, pas un
échec) et écrit **dans l'arbre de travail du dépôt déployé** : comparer les md5 avant de purger la
box, sinon le `git pull` suivant refuse de s'appliquer (#70).

## DB fait foi (ADR 0010/0022)

Le vault Obsidian est **déconnecté** : la DB PostgreSQL est seule source de vérité pour
recettes, menus, convives et stock. Plus aucun `.md`, plus aucun rclone.

| Piège | Geste |
|---|---|
| Nouvelle colonne dans un `CREATE TABLE` | L'ajouter **aussi** à `MIGRATIONS_SQL` — le VPS a déjà les tables. Un **index** sur cette colonne ne vit QUE dans la migration : `SCHEMA_SQL` s'exécute avant |
| `menu_meal.position` | 1-based en DB : tout JS fait `position - 1` |
| Modifier un repas | `POST /api/menus` **reconstruit** `menu_meal` depuis `menu.meals` et supprime le reste ; `PATCH .../meals/{id}` n'écrit QUE `menu_meal`. Les deux divergent en silence, et le POST suivant écrase le PATCH |
| Marquer un repas mangé | `POST /api/menus/{slug}/served` (day/slot), **jamais** le `PATCH` du repas |

⛔ **Jamais de `DELETE FROM menu` ni `menu_meal`** : l'API upsert, un DELETE global efface les
menus créés par l'API et la colonne `served`.

## Qui est à table

`POST /api/child-week/sync?day=` **d'abord**, puis `GET /api/attendance?day=`.

- **409** = semaine non synchronisée → lancer le sync. Ne veut **jamais** dire « enfants absents ».
- **422** = event « Semaine enfants » introuvable sur ±60 j → demander à Julien, ne pas supposer.
- Tout vient de la **DB** (`person` fait autorité, `convive` est legacy) ; la garde alternée vient de **gcal**, pas d'un calcul de semaine paire (ADR 0004).
- Repas hors domicile : lire les events bruts et **juger le sens**, jamais chercher « resto » par mot-clé.
- `POST /api/seed` ne pose `dislikes`/`forbidden` qu'à la **création** : ne pas les remettre dans son `DO UPDATE`.
- **Données mortes, ne pas raisonner dessus** : `meal_attendance`, `stay.cooking`, `extra_headcount` (#73).

## Contraintes alimentaires — quatre axes distincts

Quatre axes, détaillés dans `julien-cooking-manager-weekly-prep` § 3 : `forbidden`, `dislikes`,
`diet_exceptions` (vérifiés par `/compatibility`) et `dietary_preference`, qui **pèse sans
bloquer** et n'est compté que si sa cible est un **ingrédient nommé** ; un goût partagé par tout
le foyer s'y écrit avec `person_id NULL`.

⛔ **Quatre compteurs se lisent AVANT leur voisin rassurant** (ADR 0023, 0025) :
`preferences_unmeasurable` avant `preferences_breached` (une cible qu'aucun ingrédient ne porte,
ou un `cap` en grammes, rend `measurable: false` — son zéro ne mesure rien) ·
`conflicts_uncovered` avant `conflicts` (un conflit `repaired: true` est traité) ·
`unrepaired` avant `repairs` · `leftovers_unsourced` avant `conflicts` — un reste emprunte les
ingrédients de `menu_meal.leftovers_of`, **sans source exploitable il n'est pas contrôlé**, et
`match_kind: freestyle` dit qu'aucune source n'existe (#76).

⛔ **Un interdit se lit À UNE TABLÉE** : `/recipes/{slug}/compatibility` résout `?convives=` →
`?day=&slot=` → **les résidents** (`household_member`). `membership: guest` = contrainte
d'invité. Une **part séparée** est une DONNÉE (ADR 0037) : `recipe_ingredient.for_person_id` +
`replaces_position`, jamais une parenthèse ni une `## Notes`. Écrire la part en texte rend 422, et
**aucune route ne pose `for_person_id`** : passer par SQL, puis ne plus rejouer `POST /api/recipes`
sur ce slug — il efface la part en silence (#167). `declared_parts` LÈVE si la requête n'a pas
chargé `for_person_id` — son absence se lirait « aucune part ». Un terme alimentaire
s'écrit **au singulier** ; un terme ambigu (`roti`, `blanc`, `filet`) se déclare avec son motif
dans `CONTEXT_REQUIRED` (ADR 0007). Lire, jamais recopier : `/api/preferences`.

## Courses et garde-manger

La liste **n'est pas stockée, c'est un calcul** : `GET /api/menus/{slug}/shopping-list` la
recalcule à chaque appel (menu × tablée × stock). **La DB fait foi du stock.**

⛔ **`pack_plan.pack_known` se lit AVANT `packs`** (ADR 0038) : `null` dit « aucun format
connu pour cet aliment », jamais « un seul contenant ». Une dose ne se conditionne pas.

⛔ **Deux champs se lisent AVANT `lines`**, aveugle à eux par construction :
`slots_uncomposed` (tablée non nulle, aucun repas — lire `measured` avant `slots`) ·
`recurrent` (achats d'habitude, déjà filtrés du menu ; fréquences figées, #107).

⛔ **Une file unique tranche les deux sujets** (`/api/arbitration`, ADR 0032) : `subject` vaut
`food_key` ou `food_kind`. Seul l'étage **exact** tranche seul. `settled` + `decision: null` =
**instruit, hors référentiel**, distinct d'un sujet jamais vu ; lire `counts.pending` **avant**
`groups`. Sa file se construit depuis `pantry_item` + `recipe_ingredient` **et** les cibles de
substitution de régime, injectées hors table — sans elles le gate refusait à jamais un nom
qu'aucun refresh ne pouvait mettre en file.

⛔ **Le panier se confronte aux refus avant de partir, et c'est une table, pas une croyance**
(ADR 0032/0039) : `validate-cart` bloque sur un ban ou une ligne jamais arbitrée — un ban dont
AUCUN nom ne porte le mot visé ne frappe rien et rend `ok:true` (#115). `POST /api/cart/items`
élit au drive, sinon substitution **bornée**, sinon `status: asked` qui porte la question ; un
contenant voulu inconnu ne vaut pas « quelconque ». Lire `counts.asked` **avant** `lines`.
`push` rejoue **une ligne à la fois** et **recompte** — un `ok` du drive ne garantit aucune
quantité ; session anonyme → **409**. Transport : façade REST loopback `127.0.0.1:3853` de
`mcp-vps-auchan` (mcp-vps ADR 0009), jamais le MCP. Une préférence énoncée par Julien s'écrit en
base **tout de suite**, sinon elle n'existe pas. Le déroulé des sept états :
`julien-cooking-manager-weekly-prep` § 9.

⛔ **`pantry_item` est un JOURNAL D'ENTRÉES, pas un inventaire** : rien ne le décrémente. `ok`
dit « acheté un jour », jamais « il y en a ». Depuis ADR 0036, un `ok`/`low` sans quantité
mesurable est **refusé en 422** aux cinq écritures, et le panier ne part pas sans
`POST /api/menus/{slug}/pantry-confirm` — `validate-cart` exige son `menu_slug`. Lire
`pantry.confirmation` **avant `lines`** : `blind: true` dit qu'aucune ligne n'a été regardée.

⛔ **`normalize_name` retire découpe et pluriel, jamais un ÉTAT** : « sèches », « surgelés »,
« fraîche » changent l'identité, donc ne se fusionnent jamais. `find()` **élit une** ligne parmi
les doublons : si elle dit `out` quand une autre dit `ok`, la liste fait racheter (#118).

`outcome: inconnu` = présent mais quantité incomparable (lire `reason`). Commande drive non
retirée → `absent`. Déclarer : `PATCH /api/pantry` par **nom**, 409 sur homonyme (alors
`PUT /api/pantry/items/{id}`) — `julien-cooking-manager-pantry-update`.

## Photos

`web/media/recipes/<slug>.jpg` prime et survit au réseau. **Extension `.jpg` obligatoire**,
`ingest.py` ne scanne que celle-là (#70). Génération : `julien-cooking-donnees` § 4.

## Vocabulaire (ontologie)

Tout axe fermé vient de `data/ontology/cooking-vocabulary.yaml` → `ontology-manager` →
artefact épinglé `cooking_manager/cooking-vocabulary.json` — **jamais d'une table dans le code**.

⚠️ Le générateur a un **jeu de champs fixe** : une valeur ajoutée au seul YAML n'atteint
**pas** l'artefact, et le consommateur lit du vide sans erreur. Ajouter = deux dépôts **plus un
test**. Régénérer et propager : `julien-cooking-donnees` § 3.

⚠️ Les familles de protéine (`FAMILIES`, `SECONDARY`, `CLASSES` de `preferences.py`) sont
codées en dur, hors ontologie (#109) : un terme manquant fait mentir `rotate` et
`meals_without_protein` en silence.

⛔ **`food.kind` est un axe FERMÉ** (facette `food_kinds`, clés en anglais) : `POST`/`PUT
/api/food` rend 422 hors vocabulaire. Une famille absente = PAS INSTRUIT, jamais « aucune ».
Une famille qui en `dominates` d'autres (`fish`, `grain`) ne se pose **jamais** d'office : elle
ferait lire zéro au critère plus fin sans le dire.

## Référentiel aliment & produit

`food`, `food_form` et `product` s'écrivent par l'**API** ou en SQL, plus par le vault (#101).

⛔ **`product.nature` dit ce qu'un `food_key` vide VEUT DIRE** : `single` (aliment
conditionné) → **lacune** du référentiel ; `composite` (plusieurs ingrédients) → **normal**,
et l'API refuse de le rattacher (422). Sans elle, un plat rattaché à un ingrédient prend ses
macros et se lit comme réparé (ADR 0016).

⚠️ **Un `ciqual_code` ne se croit pas sur parole** — `pain-complet` déclarait le code du pain
**bis**. Source : `2025.09 Cooking manager/docs/metier/references/ciqual-2020.csv`. Collisions,
formes, XML ANSES, rattachement : `julien-cooking-donnees` § 2.

## Macros

`POST /api/recipes/{slug}/macros` écrit en base, le `GET` calcule seulement — et le POST
**refuse d'écrire** sous 0.95 de couverture. `nutrition.py` applique les règles du Coach
Nutrition, il n'invente rien. Non résolu ⇒
`unresolved` **avec son motif**, jamais une hypothèse. `kcal = P×4 + G×4 + L×9` ; au-delà de
5 % d'écart, montrer les deux chiffres. `food` × `food_form` en DB prime sur
`shopping_product.nutrition` (drive), et `coverage`/`conclusive` priment sur le total.

⛔ **Les macros vivent dans `food_form`, jamais dans `food`** : une ligne par forme
(`lentille` × `crues`/`cuites`). Un aliment **sans forme** n'a pas de macros et ne lève rien —
`GET /api/food` rend son compte `forms`. Un aliment dont la clé porte un mot de plus que la
recette est **invisible** à `match_entry` sans lever non plus (#117).

Pièges : `/macros` lit `_load_food_base_from_db()` (pas de cache) ; `qty_min` est un `Decimal` ;
`servings` vaut 1, 2 ou 4 selon la recette, donc deux `per_portion` ne se comparent pas (#116).

⛔ **Deux routes refusent de conclure, et c'est leur réponse** (ADR 0033) :
`/menus/{slug}/mediterranean` lit `measured` puis `out_of_reach` **avant** `criteria` — le
critère 9 (eau, thé) n'a aucun aliment, son absence n'est jamais un manque ·
`/menus/{slug}/nutrition` rend `verdict: null` et nomme ses manques dès qu'un ingrédient du
jour n'est pas compté. `target_age_days` **se lit, il ne se juge pas** : aucun seuil.

## Commande vocale · gate iOS 12 · design · MCP

MediaRecorder → `POST /api/audio` → Deepgram → Groq (intent JSON) → exécution. Intents déclarés
dans le prompt de `backend/stt.py` : un intent non câblé échoue en silence. Clés en credstore
systemd. MediaRecorder exige Safari 14.5+ : micro masqué sur iPad mini 2.

Cible **Safari 12.5.8** : le catalogue interdit → parade vit dans `julien-audit-ios12-compat`.
Vérifier `audit_ios12.py web` (score ≥ 90, zéro bloquant) ; `package.json` = devDependencies
only, **pas de build**. Aucun scanner ne voit zoom auto < 16 px, `100vh`, `:hover` — **iPad
réel seul valide.** Design : **appétissant · sans friction · maîtrisé**, letter-spacing plutôt
que graisse. `cooking_mcp.py` : `from fastmcp import FastMCP` (pas `mcp.server.fastmcp`),
v3.4+ ; derrière nginx `allowed_hosts=[<domaine>]`, sinon Starlette rend 421.

## Contraintes mesurées (ratchet)

Quatre métriques ne doivent **jamais** régresser (rattachement `single`/`composite`, plafond
`read_energy`, refus d'une `nature` inconnue). Elles ne se recopient pas ici, elles vivent dans
les tests — `python -m pytest -k "Ratchet or CompositeIsNever or ProductNature or nutrition"`.

## Skills liées
`julien-cooking-manager-weekly-prep` (semaine) · `julien-cooking-manager-pantry-update` (stock)
· `julien-cooking-donnees` (données, référentiel, ontologie) · `julien-audit-cooking-vault`
(audit avant courses) · `cooking-manager-auchan-drive` (panier Auchan).
