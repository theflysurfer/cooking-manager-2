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

`Noyau/Cuisine/` (Dropbox, monté sur le VPS via rclone) : `Recettes/*.md` · `Menus/*.md` ·
`Convives.md` · `Garde-manger.md`. Le bloc `meals:` du frontmatter fait foi, les tableaux du
corps ne sont pas lus. Slots, restes, délai du mount : `julien-ref-cooking-donnees` § 1.

| Piège | Geste |
|---|---|
| Nouvelle colonne dans un `CREATE TABLE` | L'ajouter **aussi** à `MIGRATIONS_SQL` — le VPS a déjà les tables. Un **index** sur cette colonne ne vit QUE dans la migration : `SCHEMA_SQL` s'exécute avant |
| `menu_meal.position` | 1-based en DB : tout JS fait `position - 1` |

⛔ **Jamais de `DELETE FROM menu` ni `menu_meal`** : l'ingestion upsert, un DELETE global
efface les menus créés par l'API et la colonne `served`. ⛔ **Jamais départager deux fiches
au `mtime`** — sur le mount rclone il date la copie ; `read_recipes()` tranche sur la date
déclarée. Écrire un menu de bout en bout : `julien-cooking-manager-weekly-prep` § 4 à 6.

## Qui est à table

`POST /api/child-week/sync?day=` **d'abord**, puis `GET /api/attendance?day=`.

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
protéines** : ces règles s'appliquent à la main en composant (#77 #78). Trois autres angles
morts : les repas `leftovers` (sans fiche, donc sans ingrédients à confronter, #76), les parts
séparées (« pois chiches pour Clémence » reste un conflit poulet), et `repairs` vide qui ne veut
pas dire « rien à réparer » — **lire `unrepaired`**.

Un terme alimentaire s'écrit **au singulier**, toujours : la flexion va du singulier vers le
pluriel, jamais l'inverse. Un terme ambigu (`roti`, `blanc`, `filet`) se déclare avec son motif
dans `CONTEXT_REQUIRED` (ADR 0007). Lire, jamais recopier : `/api/preferences` ·
`/api/menus/<slug>/compatibility`. Détail : `julien-cooking-manager-weekly-prep` § 3.

## Courses et garde-manger

La liste **n'est pas stockée, c'est un calcul** : `GET /api/menus/{slug}/shopping-list` la
recalcule à chaque appel (menu × tablée × stock). **La DB fait foi du stock.**

⛔ **Plus rien ne lit `Garde-manger.md`** (ADR 0017) : le stock ne bouge que sur déclaration —
`PATCH /api/pantry`, report d'un drive, ticket. Écrire dans le fichier n'atteint aucune base.

⛔ **`normalize_name` retire découpe et pluriel, jamais un ÉTAT** : « sèches », « surgelés »,
« fraîche », « entier » changent l'identité de l'aliment.

⛔ **`age_days` ne dit rien de l'âge des articles** : l'inventaire est daté par `MAX(updated_at)`,
donc une seule écriture le rajeunit tout entier. Juger sur `entered_at`, par article (#84).

⛔ **`outcome: inconnu` veut dire « présent, quantité incomparable »**, jamais « on ne sait pas
si tu l'as » : stock en texte libre, besoin en chiffres. Lire le `reason` et trancher à la main.

⛔ **Une commande drive non retirée n'est ni du stock ni un manque** : absente de
`pantry_item`, ses lignes ressortent `absent`. Lire `grocery_orders` avant de racheter — un
`status` vide veut dire « pas encore retirée ».

Déclarer l'état d'un article : `PATCH /api/pantry` (par **nom**, rend 409 sur un homonyme) —
`julien-cooking-manager-pantry-update`. Calcul, `purchase`, Auchan Drive, divergence avec le
Coach Nutrition : `julien-ref-cooking-donnees` § 5.

## Photos

Le fichier local `web/media/recipes/<slug>.jpg` prime et survit au réseau. **Extension `.jpg`
obligatoire**, `ingest.py` ne scanne que celle-là (#70). Génération et upsert protégé :
`julien-ref-cooking-donnees` § 4.

## Vocabulaire (ontologie)

Cuissons, cuisines, textures, accommodations, axes de retour et natures de produit viennent de
`data/ontology/cooking-vocabulary.yaml` → `ontology-manager` → artefact épinglé
`cooking_manager/cooking-vocabulary.json` — **jamais d'une table écrite dans le code**.

⚠️ Le générateur a un **jeu de champs fixe** (dépôt ontology-manager) : un champ ou une facette
ajouté au seul YAML n'atteint **pas** l'artefact, et le consommateur lit une valeur vide sans
erreur. Ajouter = deux dépôts **plus un test**. Régénérer et propager :
`julien-ref-cooking-donnees` § 3.

## Référentiel aliment & produit

`generiques/` → `food` · `marques/` → `product`. **Le dossier tranche**, jamais le champ
`marque` : le frontmatter est lu ligne à ligne, donc la **chaîne** `"null"` est vraie (#85).

⛔ **`product.nature` dit ce qu'un `food_key` vide VEUT DIRE** : `single` (aliment
conditionné) → c'est une **lacune** du référentiel ; `composite` (plusieurs ingrédients) →
c'est **normal**, et l'import refuse de le rattacher. Sans elle, un plat rattaché à un
ingrédient prend ses macros et se lit comme réparé (ADR 0016).

⚠️ **Un `ciqual_code` ne se croit pas sur parole** (`pain-complet` déclarait `7010`, le pain
**bis**), et une fiche corrigée en local n'atteint pas le VPS sans `rclone copy`.

Collisions, formes, XML ANSES, rattachement : `julien-ref-cooking-donnees` § 2.

## Macros

`nutrition.py` applique les règles du Coach Nutrition, il n'invente rien.

1. **Pas d'hypothèse** — non résolu ⇒ `unresolved` avec son motif. Une base sans « pour 100 g » est ignorée ; une fiche « Crues »/« Cuites » sans forme nommée ne tranche pas.
2. **Réconcilier** — `kcal = P×4 + G×4 + L×9` ; au-delà de 5 % d'écart, montrer les deux chiffres.
3. **Trois sources** — `marques/` > `shopping_product.nutrition` > `generiques/` (CIQUAL). Jamais de quatrième position implicite. `coverage`/`conclusive` priment sur le total.

⛔ **Une énergie se lit avec son unité** — les fiches écrivent « 2820 kJ (673 kcal) », et le
premier nombre est le mauvais. `read_energy()` prend les kcal si écrits, convertit les kJ
sinon, et **refuse au-delà de 950 kcal/100 g** (l'huile pure plafonne à 900).

Pièges : `load_food_base_cached()` obligatoire ; `qty_min` est un `Decimal`.

## Commande vocale

MediaRecorder → `POST /api/audio` → Deepgram → Groq (intent JSON) → exécution. Les intents
sont déclarés **dans le prompt** de `backend/stt.py` : un intent ajouté sans être câblé échoue
en silence. Clés en credstore systemd. MediaRecorder exige Safari 14.5+ : micro masqué sur
l'iPad mini 2.

## Gate iOS 12

Cible **Safari 12.5.8** : `gap` en flex, `aspect-ratio`, `<dialog>`,
`prefers-color-scheme`, `:focus-visible`, `?.`/`??`/`||=` et les champs de classe sont
hors d'atteinte. Le catalogue interdit → parade vit dans `julien-audit-ios12-compat`.

Vérifier : `audit_ios12.py web` (score ≥ 90, zéro bloquant). `package.json` est en
devDependencies : **pas de build**.

⚠️ Aucun scanner ne voit le zoom auto sur `input` < 16 px, `100vh` mouvant, `:hover`
collant. **Seul l'iPad réel valide.**

## Design

**Appétissant** (la photo mène) · **Sans friction** (quoi manger ce soir en un coup d'œil) ·
**Maîtrisé** (macros, stock, courses). Hiérarchie par le letter-spacing jamais par la graisse,
un seul accent, ni rayon ni ombre. Détail : `2026.08 Product Toolkit/research/`.

## Skills liées

- `julien-cooking-manager-weekly-prep` — **owner** — toute la semaine : tablée, menu, photos, stock, courses, macros, retours de table.
- `julien-cooking-manager-pantry-update` — **owner** — déclarer un aliment épuisé, bas ou présent, corriger une quantité, reporter un drive.
- `julien-ref-cooking-donnees` — **owner** — les chaînes de données : ingestion du vault, référentiel aliment/produit, ontologie, photos, calcul des courses.
- `julien-audit-cooking-vault` — **owner** — auditer les données ingérées, **avant** toute génération de courses.
- `cooking-manager-auchan-drive` — gros consommateur — pilote le panier depuis ces courses.

## MCP · dépendances

`cooking_mcp.py` importe `from fastmcp import FastMCP` (pas `mcp.server.fastmcp`) : seul
`fastmcp` v3.4+ expose `host`/`port`/`allowed_hosts` dans `run()`. Derrière nginx avec
`Host $host`, passer `allowed_hosts=[<domaine>]`, sinon Starlette rend 421. Un venv
reconstruit à neuf est le test de vérité des dépendances de `pyproject.toml`.
