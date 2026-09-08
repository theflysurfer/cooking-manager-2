# Cooking Manager 2

App web de cuisine familiale : recettes du vault Obsidian, menus de la semaine,
courses différentielles, macros. **Cible : iPad mini 2 / Safari 12.5.8**, en cuisine.

<!-- fast-search-directive -->
⚡ Dépôt sous Dropbox : chercher avec les outils **Grep** / **Glob** / **Read**, jamais
`grep`/`find` en bash (100 à 4000× plus lents). Bash reste bon pour git, ssh, curl, pytest.
<!-- /fast-search-directive -->

## Commandes

```bash
# Déployer (le VPS est un vrai clone git)
ssh srv759970 'cd /opt/cooking-manager-2 && git pull && .venv/bin/pip install -q . && sudo systemctl restart cooking-manager'

# L'API est derrière une basic auth nginx : toujours passer par le VPS
ssh srv759970 'curl -s localhost:8795/api/<route>'
ssh srv759970 'curl -s -X POST localhost:8795/api/ingest'          # après tout rclone copy
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

`cooking_manager/` = domaine pur, sans I/O réseau : `vault` `normalizer` `ingredients`
`convives` (compatibilité) `presence` (qui est à table) `pantry` (stock, différentiel)
`nutrition` `substitutions`. `backend/` = FastAPI, schéma, ingestion, `stt.py`, `cooking_mcp.py`.
`web/` = 3 fichiers statiques, zéro build. `data/ontology/` = source du vocabulaire.
Déploiement : systemd `cooking-manager` (8795) + `cooking-mcp` (3868) sur srv759970 ; les
tables recette appartiennent à **recipe-manager** (8796), CM2 est colocataire.

## Vault → base

`Noyau/Cuisine/` (Dropbox, monté sur le VPS via rclone). Quatre fichiers font foi : `Recettes/*.md` · `Menus/*.md` · `Convives.md` · `Garde-manger.md`.

| Règle | Geste |
|---|---|
| Le bloc `meals:` du frontmatter fait foi | Les tableaux du corps ne sont **pas** lus |
| Relier un repas à sa fiche | `<slot>_slug:` (jamais l'appariement par titre) |
| Repas de restes | `<slot>_leftovers: true` — **sans fiche**, sinon on rachète les ingrédients |
| Une recette au menu | Sa fiche `Recettes/*.md` existe **avant** le calcul des courses |
| Après un `rclone copy` | Attendre ~30 s (délai du mount), puis ré-ingérer |
| Nouvelle colonne dans un `CREATE TABLE` | L'ajouter **aussi** à `MIGRATIONS_SQL` — le VPS a déjà les tables |
| `menu_meal.position` | 1-based en DB : tout JS fait `position - 1` |

⛔ **Jamais de `DELETE FROM menu` ni `menu_meal`** : l'ingestion upsert, un DELETE global
efface les menus créés par l'API et la colonne `served`. ⛔ **Jamais départager deux fiches
au `mtime`** — sur le mount rclone il date la copie ; `read_recipes()` tranche sur la date
déclarée. Écrire un menu de bout en bout : `julien-cooking-manager-weekly-prep` § 4 à 6.

## Qui est à table

```bash
ssh srv759970 'curl -s -X POST "localhost:8795/api/child-week/sync?day=AAAA-MM-JJ"'   # D'ABORD
ssh srv759970 'curl -s "localhost:8795/api/attendance?day=AAAA-MM-JJ"'
```

- **409** = semaine non synchronisée → lancer le sync. Ne veut **jamais** dire « enfants absents ».
- **422** = event « Semaine enfants » introuvable sur ±60 j → demander à Julien, ne pas supposer.
- Tout vient de la **DB** (`person` fait autorité, `convive` est legacy) ; la garde alternée vient de **gcal**, pas d'un calcul de semaine paire (ADR 0004).
- Repas hors domicile : lire les events bruts et **juger le sens**, jamais chercher « resto » par mot-clé.
- `POST /api/seed` ne pose `dislikes`/`forbidden` qu'à la **création** : ne pas les remettre dans son `DO UPDATE`.
- **Données mortes, ne pas raisonner dessus** : `meal_attendance`, `stay.cooking`, `extra_headcount` (#73).

## Contraintes alimentaires — quatre axes distincts

| Axe | Sens | Vérifié par `/compatibility` ? |
|---|---|---|
| `person.forbidden` | ne se discute pas | ✅ |
| `person.dislikes` | aversion pour un aliment nommé | ✅ |
| `person.diet_exceptions` | ce que le régime interdit mais que la personne mange | ✅ |
| `dietary_preference` | ce qui **pèse sans bloquer** (`minimize`/`maximize`/`cap`/`rotate`/`no_restriction`) | ❌ **rien ne le lit** |

⛔ **Un menu « sans conflit » ne dit rien du gluten, des sucres ajoutés ni de la rotation des
protéines** : ces règles s'appliquent à la main en composant (`julien-cooking-manager-weekly-prep`
§ 3, #77 #78). Deux autres angles morts : les repas `leftovers` (sans fiche, donc sans ingrédients
à confronter, #76) et les parts séparées (« pois chiches pour Clémence » reste un conflit poulet).

Lire, jamais recopier : `/api/preferences` · `/api/menus/<slug>/compatibility`.

### Écrire un terme alimentaire

**Au singulier**, toujours (`DIETS`, `dislikes`, `forbidden`, `diet_exceptions`) : la flexion
va du singulier vers le pluriel, jamais l'inverse. Un terme ambigu (`roti`, `blanc`, `filet`,
`cuisse`) se déclare avec son motif dans `CONTEXT_REQUIRED`, sinon « pois chiches rôtis »
sort incompatible pescétarien (ADR 0007). Une règle nommée ne s'ajoute que sur observation —
sa raison s'affiche à l'utilisateur. Détail : `julien-cooking-manager-weekly-prep` § 3.

`repairs` vide ne veut pas dire « rien à réparer » — **lire `unrepaired`** : `RULES_BY_DIET` ne couvre qu'une minorité des termes de `DIETS`.

## Courses et garde-manger

La liste **n'est pas stockée, c'est un calcul** : `GET /api/menus/{slug}/shopping-list` la
recalcule à chaque appel (menu × tablée × stock). `shopping_session`/`shopping_product` sont
un compte rendu d'après coup, relié à aucun menu (#67, #68).

| Règle | Geste |
|---|---|
| La DB est la source de vérité du stock | Le vault n'est qu'une source d'ingestion ; `source != 'vault'` survit à la ré-ingestion (#69) |
| `normalize_name` a changé | `POST /api/pantry/renormalize?dry_run=true` puis sans — les clés stockées sont figées et désalignent le stock en silence |
| `normalize_name` retire découpe et pluriel | **Jamais un état** : « sèches », « surgelés », « fraîche », « entier » changent l'identité |
| Un appariement qu'aucune règle ne peut trancher | `POST /api/pantry/aliases` — l'alias vise un **nom** (`target_normalized`), jamais un id |
| Deux fiches nomment le même aliment autrement | `build_needs` les fusionne à famille d'unité égale ; les libellés absorbés restent dans `merged_from` |
| Une ligne de courses porte `purchase` | `mesure` · `comptable` (arrondi au-dessus) · `dose` (→ 1 conditionnement) · `non_resolu`. Le format vendu appartient au magasin (#82) |
| Auchan Drive | **Seule voie** : MCP VPS `mcp-vps-auchan` (3854). `backend/auchan*.py` est décommissionné, HydraSpecter n'est qu'un outil de diagnostic. Un panier vide + `orders` vide = session **anonyme** : lire `grocery_session_status` |

⛔ **`age_days` ne dit rien de l'âge des articles** : l'inventaire est daté par `MAX(updated_at)`,
donc une seule écriture le rajeunit tout entier. Juger la fraîcheur sur `entered_at`, par article (#84).

⛔ **`outcome: inconnu` veut dire « présent, quantité incomparable »**, jamais « on ne sait pas
si tu l'as » : stock en texte libre, besoin en chiffres. Lire le `reason` et **trancher à la
main** — un humain compare « 1 » à « 8 pièces » là où le calcul ne peut pas.

⛔ **Une commande drive non retirée n'est ni du stock ni un manque** : absente de
`pantry_item`, toutes ses lignes ressortent `absent`. Lire `grocery_orders` avant de racheter —
un `status` vide veut dire « pas encore retirée ».

Déclarer l'état d'un article : `PATCH /api/pantry` (par **nom**, écrit en base, rend 409 sur
un homonyme). Détail et pièges : `julien-cooking-manager-pantry-update`.

⚠️ **`Garde-manger.md` est aussi lu et écrit par le Coach Nutrition de claude.ai**, qui n'appelle jamais l'app : les deux stocks divergent sans alerte. Croiser via `pantry_item` (DB).

## Photos

Une photo distante est en sursis : le fichier local `web/media/recipes/<slug>.jpg` prime et
survit au réseau. **Extension `.jpg` obligatoire**, `ingest.py` ne scanne que celle-là (#70).
Générer via recipe-manager, jamais un prompt improvisé (versionné v1.1 chez lui) :
`POST localhost:8796/recipes/<slug>/generate-image?inline=true` → écrire dans
`web/media/recipes/`, **committer**, `git pull` sur le VPS.

L'upsert garde `photo_url=COALESCE($24, recipe.photo_url)` : sinon un scraping en échec efface la photo.

## Vocabulaire (ontologie)

Cuissons, cuisines, textures, accommodations et axes de retour viennent de
`data/ontology/cooking-vocabulary.yaml` → `ontology-manager` → artefact épinglé
`cooking_manager/cooking-vocabulary.json` — **jamais d'une table écrite dans le code**.
Régénérer : `python -m ontology_manager.cli generate --ontology cooking-vocabulary`, puis
recopier l'artefact.

⚠️ Le générateur a un **jeu de champs fixe** (dépôt ontology-manager) : un champ ajouté au
YAML n'atteint pas l'artefact, et le consommateur lit une valeur vide sans erreur. Ajouter un
champ = toucher les deux dépôts **plus un test**. `dominates` : n'y inscrire que l'observé.

## Référentiel aliment & produit

`generiques/` → `food` · `marques/` → `product`. **Le dossier tranche**, jamais le
champ `marque` : 49 fiches génériques portent `marque: null`, et le frontmatter étant
lu ligne à ligne, la **chaîne** `"null"` est vraie (#85 — même piège sur `bio: true`,
`ciqual_code: 7010`, toute liste YAML).

| Règle | Geste |
|---|---|
| Deux fiches sur une même clé normalisée | Ni l'une ni l'autre n'est importée — elles sortent dans `collisions`, à trancher à la main |
| Une fiche à plusieurs formes (« Crues »/« Cuites ») | Sans forme neutre `100g`, elle part en `skipped` avec son motif |
| Avant toute bascule de consommateur | `GET /api/food/report` : `missing` **et** `macro_mismatch` vides (ADR 0011) |
| Un produit non rattaché | `status = 'a_rapprocher'` — un choix à faire, jamais un oubli |
| `product.nature` avant tout rapprochement | `single` = conditionnement d'un aliment (un `food_key` vide est une **lacune**) · `composite` = plusieurs ingrédients (un `food_key` vide est **normal**). Rattacher un composite donne les macros d'un ingrédient au plat entier, et le fait sortir du compteur (ADR 0016) |

⛔ **Les fiches ne portent pas d'unité d'usage** (1 fiche sur 248, mesuré le 2026-09-07) :
une « Portion courante » est un contexte de repas, pas une unité — ne pas la convertir
en `food_unit`.

⚠️ **Une fiche corrigée en local ne suffit pas** — le VPS monte le cloud : propager par
`rclone copy` **et** `rclone delete`. Un `directory not found` signale une syntaxe fausse,
jamais une absence.

⚠️ **Un `ciqual_code` ne se croit pas sur parole** (`pain-complet` déclarait `7010`, le pain
**bis**). Vérifier dans le XML ANSES de data.gouv.fr — il est en **cp1252** et casse tout
parseur XML, le lire par regex. Les sites tiers mélangent les millésimes. ADR 0011.

## Macros

`nutrition.py` applique les règles du Coach Nutrition (`Noyau/Coaches/Coach Nutrition/_coach.md`),
il n'invente rien.

1. **Pas d'hypothèse** — non résolu ⇒ `unresolved` avec son motif. Une base sans « pour 100 g » est ignorée ; une fiche « Crues »/« Cuites » sans forme nommée ne tranche pas.
2. **Réconcilier** — `kcal = P×4 + G×4 + L×9` ; au-delà de 5 % d'écart, montrer les deux chiffres.
3. **Trois sources** — `marques/` > `shopping_product.nutrition` > `generiques/` (CIQUAL). Jamais de quatrième position implicite. `coverage`/`conclusive` priment sur le total.

Pièges : `load_food_base_cached()` obligatoire ; `qty_min` est un `Decimal`.

## Commande vocale

MediaRecorder → `POST /api/audio` → Deepgram → Groq (intent JSON) → exécution. Les intents
sont déclarés **dans le prompt** de `backend/stt.py` : un intent ajouté sans être câblé échoue
en silence. Clés en credstore systemd (`deploy/run-with-cred.sh`). MediaRecorder exige
Safari 14.5+ : le micro est masqué sur l'iPad mini 2.

## Gate iOS 12

Cible **Safari 12.5.8** : `gap` en flex, `aspect-ratio`, `<dialog>`,
`prefers-color-scheme`, `:focus-visible`, `?.`/`??`/`||=` et les champs de classe sont
hors d'atteinte. Le catalogue interdit → parade vit dans `julien-audit-ios12-compat`.

Vérifier : `python ~/.claude/skills/julien-audit-ios12-compat/scripts/audit_ios12.py web`
(score ≥ 90 et zéro bloquant). `package.json` est en devDependencies : **pas de build**.

⚠️ Aucun scanner ne voit le zoom auto sur `input` < 16 px, `100vh` mouvant, `:hover`
collant. **Seul l'iPad réel valide.**

## Design

**Appétissant** (la photo mène) · **Sans friction** (quoi manger ce soir en un coup d'œil) ·
**Maîtrisé** (macros, stock, courses). Hiérarchie par le letter-spacing jamais par la graisse,
un seul accent, ni rayon ni ombre. Détail : `2026.08 Product Toolkit/research/`.
## Skills liées

- `julien-cooking-manager-weekly-prep` — **owner** — toute la semaine : tablée, menu écrit et contrôlé, photos, stock, courses, macros, retours de table.
- `julien-cooking-manager-pantry-update` — **owner** — déclarer un aliment épuisé, bas ou présent, corriger une quantité, reporter un drive ; écrit en base.
- `julien-audit-cooking-vault` — **owner** — auditer les données ingérées, **avant** toute génération de courses.
- `cooking-manager-auchan-drive` — gros consommateur — pilote le panier depuis ces courses.

## MCP · dépendances

`cooking_mcp.py` importe `from fastmcp import FastMCP` (pas `mcp.server.fastmcp`) : seul
`fastmcp` v3.4+ expose `host`/`port`/`allowed_hosts` dans `run()`. Derrière nginx avec
`Host $host`, passer `allowed_hosts=[<domaine>]`, sinon Starlette rend 421.
`httpx`/`selectolax`/`mcp` sont déclarés dans `pyproject.toml` — un venv reconstruit à neuf
est le test de vérité.
