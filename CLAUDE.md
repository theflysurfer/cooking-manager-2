# Cooking Manager 2

Web app pour parcourir et filtrer les recettes familiales depuis le vault Obsidian.

## Stack

- **Backend** : FastAPI + asyncpg (PostgreSQL)
- **Frontend** : vanilla JS, **zéro build** — fichiers statiques servis par FastAPI
- **DB** : `postgresql-shared` (Docker) → database `cooking_manager`, user `cooking`
- **Recipe model** : propriété de `recipe-manager` (port 8796) — CM2 lit/écrit les tables recettes en direct (colocataire), ne les crée pas
- **Deploy** : systemd `cooking-manager.service` (Requires=recipe-manager.service) + nginx sur srv759970, port 8795
- **MCP** : `cooking-mcp.service` port 3868, `https://cooking-mcp.srv759970.hstgr.cloud/mcp`, user `mcp-run`, Google OAuth (`build_google_auth("cooking")` depuis `/home/automation/shared/mcp_auth.py`)

⚠️ **Cible : iPad mini 2 / Safari 12.5.8**, utilisé en cuisine. Ce n'est pas un
plancher de compatibilité théorique : l'ancien front y était littéralement cassé
(le `<dialog>` de la fiche recette ne s'ouvrait jamais, tous les `gap` flex
s'effondraient à 0, le thème sombre était mort). Voir § Gate iOS 12.

## Architecture

```
cooking_manager/   # Domaine pur, sans I/O réseau
  vault.py         # lecture des .md du vault
  normalizer.py    # frontmatter FR → canonique EN, slugs, dates
  ingredients.py   # corps markdown → ingrédients + étapes structurés
  convives.py      # profils alimentaires + contrôle de compatibilité
  presence.py      # qui est à table (garde alternée × vacances × absences)
backend/           # FastAPI + schéma DB + ingestion
  stt.py           # pipeline vocal : Deepgram (STT) + Groq LLM (intent)
  cooking_mcp.py   # serveur FastMCP (stdio) — garde-manger, recettes, menus
web/               # Front : index.html + style.css + app.js (+ media/recipes/)
tests/             # unitaires · gate compat iOS 12 · e2e (opt-in)
data/              # sessions de courses + photo-prompt.md (versionné)
docs/veille/       # analyses concurrentielles (auditées par julien-audit-competitor)
```

## Les 3 principes de design

Un par couche de Norman (cf. `2026.08 Product Toolkit/research/EMOTIONAL_DESIGN_METHODS.md`) :

- **Appétissant** *(viscéral)* — la photo mène, le chrome s'efface, la couleur vient des plats
- **Sans friction** *(comportemental)* — savoir quoi manger ce soir en un coup d'œil
- **Maîtrisé** *(réflectif)* — macros, garde-manger et courses sous contrôle

Tokens dérivés de healthyfoodcreation.fr : hiérarchie par le **letter-spacing**,
jamais par la graisse (Montserrat reste en 400 partout), un seul accent, ni
rayon ni ombre — la carte est une image posée sur du blanc.

## Commandes

```bash
# Build cuisine.json (legacy, standalone)
python -m cooking_manager build --vault /path/to/Cuisine

# Run web server
python -m cooking_manager serve --port 8795

# Deploy on VPS — /opt/cooking-manager-2 est un vrai clone git (depuis 2026-08-04)
ssh srv759970 'cd /opt/cooking-manager-2 && git pull && .venv/bin/pip install -q . && sudo systemctl restart cooking-manager'
```

## Vault source

Le vault Obsidian `Noyau/Cuisine/` est dans Dropbox, monté en lecture sur le VPS via rclone (`/mnt/dropbox-full/JULIEN/Obsidian/vault/Noyau/Cuisine`). L'ingestion est déclenchée via `POST /api/ingest`.

Quatre fichiers font autorité, dans cet ordre de spécificité :

| Fichier | Porte | Ingéré vers |
|---|---|---|
| `Recettes/*.md` | recettes + ingrédients + étapes (dans le corps) | `recipe`, `recipe_ingredient`, `recipe_step` |
| `Menus/*.md` | **le bloc `meals:` du frontmatter** fait foi, pas les tableaux du corps | `menu.meals` (JSONB) + `menu_meal` |
| `Convives.md` | régimes, interdits, cuissons d'œufs refusées, aversions | `convive` |
| `Garde-manger.md` | stock réel par rayon, statuts, quantités | `pantry_item` (DB = source de vérité) |
| `Presences.md` | ⚠️ **plus lu par l'app depuis 2026-08-12** — présence 100 % DB (`school_period`, `absence`, `stay`). Conservé comme note humaine seulement | — |

⚠️ **`menu.slug` est la clé naturelle.** Sans elle, l'ingestion se protégeait des
doublons par un `DELETE FROM menu` qui effaçait tout menu absent du vault — un
menu créé via l'API disparaissait à la première ingestion de recettes, sans
erreur ni trace. Ne jamais réintroduire ce DELETE.

### Relier un repas à sa recette — deux marqueurs dans `meals:`

Chaque repas est éclaté en une ligne `menu_meal` (menu × jour × créneau) à
l'ingestion, et sa recette résolue. L'appariement par titre échoue toujours
parce que l'intitulé du menu, rédigé à la main, diverge du titre de la fiche.
D'où deux marqueurs par créneau :

| Marqueur | Effet |
|---|---|
| `<slot>_slug: <recipe-slug>` | **désigne** la fiche explicitement — court-circuite l'heuristique. La seule liaison qui ne redérive pas. Un slug inconnu est journalisé, jamais silencieux. |
| `<slot>_leftovers: true` | repas de **restes**, sans fiche PAR CONCEPTION — lui en donner une ferait racheter les ingrédients du repas recyclé. Rendu dans `meals_leftovers`, pas `meals_unmatched`. |

⚠️ **Une recette au menu doit avoir sa fiche `Recettes/*.md` AVANT le calcul des
courses** — l'app ne lit QUE les fiches. Les recettes de la semaine vivent
parfois dans le **panier** (`data/shopping_choices_*.json`, chaque article porte
son repas) et pas dans `Recettes/` : générer les fiches manquantes depuis le
panier, ingrédients ancrés sur l'acheté (jamais inventés). *(Incident 2026-08-04 :
1 repas relié sur 20 — les 19 autres avaient été commandés mais jamais transcrits
en fiches.)*

## Compatibilité alimentaire — ne pas la vérifier à la main

```bash
curl -s https://cooking.srv759970.hstgr.cloud/api/menus/<slug>/compatibility
```

Croise **qui est réellement à table** (`Presences.md`) et **ce que chacun ne peut
pas manger** (`Convives.md`). Les deux sont nécessaires : la grille type de
`Convives.md` dit « mardi midi, enfants à la cantine » mais porte la mention
*« hors vacances scolaires »* — en août elle ne s'applique pas, et raisonner
dessus donne une réponse fausse avec l'aplomb d'une règle écrite.

L'agenda Google **ne suffit pas** comme source : mesuré le 2026-08-04, la semaine
ne portait qu'un seul événement. Il apporte les exceptions, jamais la trame.

## Commande vocale (STT + LLM)

Pipeline : MediaRecorder (front) → `POST /api/audio` → Deepgram prerecorded (STT) → Groq LLM (intent JSON) → exécution. Panneau `#mic-panel` affiche la transcription et l'action interprétée.

- **LLM intent** : Groq `qwen/qwen3.6-27b` (`reasoning_effort: "none"`, ~300 ms). Ollama cloud en fallback si `GROQ_API_KEY` absent
- **Credentials** : credstore systemd (`cooking-deepgram-key`, `cooking-ollama-key`, `groq-key` partagé avec bibliotheque), lues par `deploy/run-with-cred.sh`
- **MediaRecorder** exige Safari 14.5+ — le FAB micro est **masqué** sur Safari 12 (feature-detect). Le panneau vocal n'apparaît jamais sur l'iPad mini 2
- **9 intents** (tous câblés) : `search_recipe`, `adjust_servings`, `swap_recipe`, `pantry_bulk_update`, `product_blacklist`, `recipe_note`, `recipe_edit_step`, `meal_feedback`, `pantry_leftover`

## Gotchas

- **Auchan Drive : une seule voie de connexion — le MCP VPS** (`mcp-vps-auchan`, port 3854 ; décision 2026-08-12, refs #60). `backend/auchan.py`, `backend/auchan_mcp.py` et `backend/auchan_stores.py` ont été **décommissionnés le 2026-08-09** (commit `0d36988`) — leur logique de contexte magasin (`POST /journey/update`) a été portée dans le MCP VPS le 2026-08-12 (`grocery_find_stores`/`grocery_set_store`, mcp-vps#171). La session Auchan du VPS est gérée par le seul **Cookie Health VPS**. HydraSpecter = outil de diagnostic, pas une voie de connexion
- **Tablée : câblée et 100 % DB depuis 2026-08-12 (refs #33)**. `/api/menus/<slug>/compatibility` ne lit **plus** `Presences.md` ni `Convives.md` — tout vient de la DB via `load_referential_from_db()` (school_period, absence, stay, overrides) et `load_convives_from_db()` (profils depuis `person`). Résolution de présence à 4 niveaux dans `presence.py::attendees()` : **override manuel > séjour (`stay`) > trame garde/cantine > absences**. Le modèle **`stay`+`stay_member`** (tables ajoutées 2026-08-12) corrige le bug fondateur F.30 (Bègles) : en location de vacances on cuisine sur place, donc les membres du séjour sont à table quels que soient les absences et la trame. Endpoint résolveur : `GET /api/attendance?day=&slot=`. Les constantes `ADULTS`/`CHILDREN`/`CUSTODY_REFERENCE_WEEK` restent en **fallback** quand aucune `HouseholdConfig` DB n'est fournie. `convive` (legacy) et `person` coexistent encore ; `person` fait autorité pour la compatibilité. ⚠️ **Après `POST /api/seed`, relancer si besoin — idempotent** ; le séjour Bègles y est seedé (membres = foyer, Julien ajoute les invités via `stay_add`/`POST /api/stays/<id>/members/<pid>`)
- **Une photo qui n'est pas un fichier local est une photo en sursis.** `_scrape_photo()`
  reconstruit `photo_url` à chaque ingestion depuis un site tiers (timeout 8 s) : l'upsert
  écrivait `photo_url=$24` sans condition, donc **un scraping qui échoue effaçait la photo**,
  sans erreur ni warning (le 2026-08-12 : 11 recettes d'un coup, 9 au menu). Corrigé par
  `photo_url=COALESCE($24, recipe.photo_url)`. La parade de fond reste le **fichier local** :
  `web/media/recipes/<slug>.jpg` → rattachement déterministe, prioritaire sur le scraping,
  insensible au réseau. Générer les manquantes via **recipe-manager**
  (`POST /recipes/<slug>/generate-image`, port 8796), qui porte le prompt v1.1 — jamais un
  prompt improvisé, sinon le parc perd son unité visuelle et la grille se disloque. Le
  fichier écrit vit sur la box : récupérer avec `?inline=true` → `image_base64`, écrire dans
  `web/media/recipes/`, **committer**. `data/photo-prompt.md` documente le pourquoi mais ne
  pilote plus rien. Extension **`.jpg` obligatoire** :
  `ingest.py` ne scanne que celle-là, un `.png` déposé n'est jamais rattaché
- `httpx`/`selectolax`/`mcp` sont des dépendances déclarées dans `pyproject.toml` — un venv reconstruit à neuf (`pip install .`) est le test de vérité si ce fichier dérive
- Toute nouvelle colonne dans un CREATE TABLE doit aussi etre dans MIGRATIONS_SQL (`ALTER TABLE ADD COLUMN IF NOT EXISTS`) — le VPS a deja les tables, `CREATE TABLE IF NOT EXISTS` ne rajoute rien
- `menu_meal.position` est **1-based** en DB (`enumerate(meals, start=1)`) — tout consommateur JS doit faire `position - 1` pour indexer le tableau `menu.meals[]`
- Après un `rclone copy` vers Dropbox, le mount VPS (`/mnt/dropbox-full`) peut avoir un délai de propagation (~30 s) — relancer `POST /api/ingest` si une recette n'apparaît pas
- `_pantry_from_db()` remplace `_load_pantry()` — le différentiel courses lit désormais la DB, plus le Markdown
- Pour le garde-manger, la **DB est la source de vérité** (pas le vault). Le vault est une source d'ingestion parmi d'autres (API, voix). Les items `source != 'vault'` survivent à la ré-ingestion
- `cooking_mcp.py` importe `from fastmcp import FastMCP` (pas `from mcp.server.fastmcp`) — seul le package `fastmcp` (v3.4+) expose `host`/`port`/`allowed_hosts` dans `run()`. Le package `mcp` v2 a un `FastMCP.run()` minimaliste
- Tout MCP VPS derrière nginx avec `Host $host` doit passer `allowed_hosts=[<domaine>]` à `mcp.run()`, sinon Starlette retourne 421

## Gates avant commit — les trois sont bloquants

```bash
python -m ruff check cooking_manager/ backend/ tests/   # All checks passed!
python -m pyright                                        # 0 errors
python -m pytest tests/                                  # unitaires + gate compat

# Gate iOS 12 — obligatoire dès qu'on touche à web/
python ~/.claude/skills/julien-audit-ios12-compat/scripts/audit_ios12.py web
# → score ≥ 90 et ZÉRO bloquant, sinon exit 1
```

### Tests — trois étages

```bash
pytest              # unitaires + gate compat (rapide, aucun réseau)
pytest -m e2e       # frappe l'API RÉELLE du VPS — opt-in, écrit en production
```

Les e2e créent des objets préfixés `test-e2e-` et les suppriment ; un test
d'hygiène échoue si un résidu subsiste. Ils sont opt-in précisément parce qu'ils
écrivent en production.

## Gate iOS 12

Le front cible Safari 12.5.8. Parades imposées à l'écriture, vérifiées par le
scanner :

| Interdit | Parade |
|---|---|
| `gap` en **flex** (14.5) | Grid + `gap`, ou `> * + *` |
| `aspect-ratio` (15) | `padding-bottom: 52.6%` + enfant absolu |
| `<dialog>` / `showModal()` (15.4) | vue plein écran routée |
| `@media (prefers-color-scheme)` (13) | attribut `data-theme` sur `<html>` |
| `:focus-visible` · `text-wrap` · `loading="lazy"` | retirer |
| `?.` `??` `||=` · champs de classe (16) | `&&` / `||`, écriture explicite |
| `clamp()` seul | **repli déclaré AVANT** — sinon la règle est jetée en silence |

`.browserslistrc` cible `ios_saf 12.2-12.5` (seules les **bornes** de plage sont
aliasées : `12.3` renvoie *Unknown version*). `package.json` est en
**devDependencies uniquement** — il n'y a pas de build et il ne faut pas en ajouter.

⚠️ Aucun scanner ne voit les comportements propres à iOS (zoom auto sur `input`
< 16 px, `100vh` mouvant, `:hover` collant). **Seul l'iPad réel valide.**
