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

| Règle | Pourquoi ça ne se voit pas sinon |
|---|---|
| **Au singulier**, toujours (`DIETS`, `dislikes`, `forbidden`, `diet_exceptions`) | La flexion va du singulier vers le pluriel, jamais l'inverse : « lardons » ne rencontre pas « lardon » |
| Un terme **ambigu** se déclare avec son motif dans `CONTEXT_REQUIRED` | `roti` en mot nu déclare « pois chiches rôtis » incompatible pescétarien (ADR 0007). Même piège sur `blanc`, `filet`, `cuisse` |
| Une règle de `substitutions.py` avec `cuisines` se borne par `rule_applies()` | Sinon une règle ouest-africaine gagne sur un coq au vin |
| Une règle **nommée** ne s'ajoute que sur observation | Sa raison s'affiche à l'utilisateur ; inventée, elle ment. Sinon : laisser le repli, qui se déclare comme tel |

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
| Auchan Drive | **Seule voie** : MCP VPS `mcp-vps-auchan` (3854). `backend/auchan*.py` est décommissionné, HydraSpecter n'est qu'un outil de diagnostic |

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
YAML n'atteint pas l'artefact, et le consommateur lit une valeur vide sans erreur. Ajouter
un champ = toucher les deux dépôts **plus un test** qui prouve qu'il survit à la génération.
`dominates` : une cuisson préparatoire n'est pas celle du plat — n'y inscrire **que ce qui
a été observé**.

## Macros

`nutrition.py` applique les règles du Coach Nutrition (`Noyau/Coaches/Coach Nutrition/_coach.md`),
il n'invente rien.

1. **Pas d'hypothèse** — non résolu ⇒ `unresolved` avec son motif. Une base sans « pour 100 g » est ignorée ; une fiche « Crues »/« Cuites » sans forme nommée ne tranche pas.
2. **Réconcilier** — `kcal = P×4 + G×4 + L×9` ; au-delà de 5 % d'écart, montrer les deux chiffres.
3. **Trois sources** — `marques/` > `shopping_product.nutrition` > `generiques/` (CIQUAL). Jamais de quatrième position implicite.

`coverage`/`conclusive` priment sur le total (cas de refus : `julien-audit-cooking-vault`).
Pièges : `load_food_base_cached()` obligatoire ; `qty_min` est un `Decimal`.

## Commande vocale

MediaRecorder → `POST /api/audio` → Deepgram (STT) → Groq (intent JSON) → exécution. Les
intents sont déclarés **dans le prompt** de `backend/stt.py`, pas dans une table : un intent
ajouté sans être câblé échoue en silence. Clés en credstore systemd
(`deploy/run-with-cred.sh`), jamais de `.env` en clair. MediaRecorder exige Safari 14.5+, le
micro est donc masqué sur l'iPad mini 2.

## Gate iOS 12

| Interdit | Parade |
|---|---|
| `gap` en **flex** (14.5) | Grid + `gap`, ou `> * + *` |
| `aspect-ratio` (15) | `padding-bottom: 52.6%` + enfant absolu |
| `<dialog>` / `showModal()` (15.4) | vue plein écran routée |
| `@media (prefers-color-scheme)` (13) | attribut `data-theme` sur `<html>` |
| `:focus-visible` · `text-wrap` · `loading="lazy"` | retirer |
| `?.` `??` `\|\|=` · champs de classe (16) | `&&` / `\|\|`, écriture explicite |
| `clamp()` seul | repli déclaré **avant** — sinon la règle est jetée en silence |

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
- `julien-audit-cooking-vault` — **owner** — auditer les données ingérées, **avant** toute génération de courses.
- `cooking-manager-auchan-drive` — gros consommateur — pilote le panier depuis ces courses.

## MCP · dépendances

`cooking_mcp.py` importe `from fastmcp import FastMCP` (pas `mcp.server.fastmcp`) : seul
`fastmcp` v3.4+ expose `host`/`port`/`allowed_hosts` dans `run()`. Derrière nginx avec
`Host $host`, passer `allowed_hosts=[<domaine>]`, sinon Starlette rend 421.
`httpx`/`selectolax`/`mcp` sont déclarés dans `pyproject.toml` — un venv reconstruit à neuf
est le test de vérité.
