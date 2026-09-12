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
corps ne sont pas lus. Slots, restes, délai du mount : `julien-cooking-donnees` § 1.

| Piège | Geste |
|---|---|
| Nouvelle colonne dans un `CREATE TABLE` | L'ajouter **aussi** à `MIGRATIONS_SQL` — le VPS a déjà les tables. Un **index** sur cette colonne ne vit QUE dans la migration : `SCHEMA_SQL` s'exécute avant |
| `menu_meal.position` | 1-based en DB : tout JS fait `position - 1` |
| Marquer un repas mangé | `POST /api/menus/{slug}/served` (day/slot), **jamais** le `PATCH` du repas |

⛔ **Jamais de `DELETE FROM menu` ni `menu_meal`** : l'ingestion upsert, un DELETE global
efface les menus créés par l'API et la colonne `served`. ⛔ **Jamais départager deux fiches
au `mtime`** — sur le mount rclone il date la copie ; `read_recipes()` tranche sur la date
déclarée. Menu de bout en bout : `weekly-prep` § 4-6. ⛔ **Recette écrite via l'API sur un slug
ayant une fiche `.md` = écrasée au prochain ingest** (dual-writer en cours de bascule, ADR 0020).

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

⛔ **`pantry_item` est un JOURNAL D'ENTRÉES, pas un inventaire** : rien ne le décrémente, aucun
repas servi ne retire rien. `ok` répond « quelqu'un l'a acheté un jour », jamais « il y en a » —
et un `out` n'est pas plus fiable. **Faire confirmer avant de composer dessus** (#94). Corollaire :
un `insuffisant` en cours de semaine additionne les repas déjà mangés, ne pas racheter dessus.
Plus rien ne lit `Garde-manger.md` (ADR 0017) : le stock ne bouge que sur déclaration.

⛔ **`normalize_name` retire découpe et pluriel, jamais un ÉTAT** : « sèches », « surgelés »,
« fraîche », « entier » changent l'identité de l'aliment.

Fraîcheur **par article** sur `entered_at` : périssable > 14 j ou sans date → `inconnu`.
`outcome: inconnu` = présent mais quantité incomparable (lire `reason`). Commande drive non
retirée → `absent` en courses (lire `grocery_orders` avant de racheter). Déclarer : `PATCH /api/pantry`
par **nom**, 409 sur homonyme — `julien-cooking-manager-pantry-update` · calcul et drive : `julien-cooking-donnees` § 5.

## Photos

Le fichier local `web/media/recipes/<slug>.jpg` prime et survit au réseau. **Extension `.jpg`
obligatoire**, `ingest.py` ne scanne que celle-là (#70). Génération et upsert protégé :
`julien-cooking-donnees` § 4.

## Vocabulaire (ontologie)

Cuissons, cuisines, textures, accommodations, axes de retour et natures de produit viennent de
`data/ontology/cooking-vocabulary.yaml` → `ontology-manager` → artefact épinglé
`cooking_manager/cooking-vocabulary.json` — **jamais d'une table écrite dans le code**.

⚠️ Le générateur a un **jeu de champs fixe** (dépôt ontology-manager) : un champ ou une facette
ajouté au seul YAML n'atteint **pas** l'artefact, et le consommateur lit une valeur vide sans
erreur. Ajouter = deux dépôts **plus un test**. Régénérer et propager :
`julien-cooking-donnees` § 3.

## Référentiel aliment & produit

`generiques/` → `food` · `marques/` → `product`. **Le dossier tranche**, jamais le champ
`marque`. Le parser frontmatter (`parse_food_sheet`) sanitise `null`/`none`/`nan`/`-`/`n/a`/`~`
en `None` — plus de chaîne `"null"` truthy (#85 fixé).

⛔ **`product.nature` dit ce qu'un `food_key` vide VEUT DIRE** : `single` (aliment
conditionné) → c'est une **lacune** du référentiel ; `composite` (plusieurs ingrédients) →
c'est **normal**, et l'import refuse de le rattacher. Sans elle, un plat rattaché à un
ingrédient prend ses macros et se lit comme réparé (ADR 0016).

⚠️ **Un `ciqual_code` ne se croit pas sur parole** (`pain-complet` déclarait `7010`, le pain
**bis**), et une fiche corrigée en local n'atteint pas le VPS sans `rclone copy`.

Collisions, formes, XML ANSES, rattachement : `julien-cooking-donnees` § 2.

## Macros

`nutrition.py` applique les règles du Coach Nutrition, il n'invente rien.

1. **Pas d'hypothèse** — non résolu ⇒ `unresolved` avec son motif. Une base sans « pour 100 g » est ignorée ; une fiche « Crues »/« Cuites » sans forme nommée ne tranche pas.
2. **Réconcilier** — `kcal = P×4 + G×4 + L×9` ; au-delà de 5 % d'écart, montrer les deux chiffres.
3. **Trois sources** — `marques/` > `shopping_product.nutrition` > `generiques/` (CIQUAL). Jamais de quatrième position implicite. `coverage`/`conclusive` priment sur le total.

⛔ **Une énergie se lit avec son unité** — les fiches écrivent « 2820 kJ (673 kcal) », et le
premier nombre est le mauvais. `read_energy()` prend les kcal si écrits, convertit les kJ
sinon, et **refuse au-delà de 950 kcal/100 g** (l'huile pure plafonne à 900).

Pièges : `/macros` lit la table `food` en DB (pas le vault .md) ; `qty_min` est un `Decimal`.
Décommissionnement complet du vault .md aliments : #95.

## Commande vocale

MediaRecorder → `POST /api/audio` → Deepgram → Groq (intent JSON) → exécution.
Intents déclarés dans le prompt de `backend/stt.py` : un intent non câblé échoue en silence.
Clés en credstore systemd. MediaRecorder exige Safari 14.5+ : micro masqué sur iPad mini 2.

## Gate iOS 12

Cible **Safari 12.5.8** : `gap` en flex, `aspect-ratio`, `<dialog>`,
`prefers-color-scheme`, `:focus-visible`, `?.`/`??`/`||=` et les champs de classe sont
hors d'atteinte. Le catalogue interdit → parade vit dans `julien-audit-ios12-compat`.

Vérifier : `audit_ios12.py web` (score ≥ 90, zéro bloquant). `package.json` = devDependencies
only, **pas de build**. Aucun scanner ne voit zoom auto < 16 px, `100vh`, `:hover` — **iPad réel seul valide.**

## Design

**Appétissant** · **Sans friction** · **Maîtrisé**. Letter-spacing, pas graisse.

## Skills liées

- `julien-cooking-manager-weekly-prep` — semaine : tablée, menu, photos, stock, courses, macros, retours.
- `julien-cooking-manager-pantry-update` — stock : déclarer épuisé/bas/présent, corriger quantité, drive.
- `julien-cooking-donnees` — données : ingestion vault, référentiel, ontologie, photos, courses.
- `julien-audit-cooking-vault` — auditer les données ingérées avant génération de courses.
- `cooking-manager-auchan-drive` — pilote le panier Auchan depuis les courses.

## Contraintes mesurées (ratchet)

| Métrique | Valeur | Direction | Vérifié par |
|---|---|---|---|
| `single` products sans `food_key` | 0 | must stay 0 | `pytest tests/test_food_import.py::TestLinkingRatchet` |
| `composite` jamais rattaché | 0 linked | must stay 0 | `pytest tests/test_food_import.py::TestCompositeIsNeverLinked` |
| `read_energy` plafond | 950 kcal | must not rise | `pytest tests/test_nutrition.py` |
| `nature` inconnue refusée | ValueError | must stay | `pytest tests/test_food_import.py::TestProductNature` |

Toute régression sur ces métriques casse `python -m pytest` → bloque le ship.

## MCP · dépendances

`cooking_mcp.py` : `from fastmcp import FastMCP` (pas `mcp.server.fastmcp`), v3.4+.
Derrière nginx : `allowed_hosts=[<domaine>]`, sinon Starlette rend 421.
