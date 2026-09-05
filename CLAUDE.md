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
data/              # courses + photo-prompt.md + ontology/cooking-vocabulary.yaml (SOURCE)
docs/veille/       # analyses concurrentielles (auditées par julien-audit-competitor)
```

## Les 3 principes de design

Un par couche de Norman : **Appétissant** *(viscéral, la photo mène)* ·
**Sans friction** *(comportemental, quoi manger ce soir en un coup d'œil)* ·
**Maîtrisé** *(réflectif, macros/garde-manger/courses sous contrôle)*. Tokens
dérivés de healthyfoodcreation.fr — hiérarchie par letter-spacing, jamais par
la graisse, un seul accent, ni rayon ni ombre. Détail :
`2026.08 Product Toolkit/research/EMOTIONAL_DESIGN_METHODS.md`.

## Commandes

```bash
# Build cuisine.json (legacy, standalone)
python -m cooking_manager build --vault /path/to/Cuisine

# Run web server
python -m cooking_manager serve --port 8795

# Deploy on VPS — /opt/cooking-manager-2 est un vrai clone git (depuis 2026-08-04)
ssh srv759970 'cd /opt/cooking-manager-2 && git pull && .venv/bin/pip install -q . && sudo systemctl restart cooking-manager'

# Interroger la DB sans credentials — /api/ est derriere une basic auth nginx (401 != panne)
ssh srv759970 'docker exec postgresql-shared psql -U cooking -d cooking_manager -c "SELECT ..."'
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

⚠️ **`menu.slug` est la clé naturelle.** Ne jamais réintroduire le
`DELETE FROM menu` qui protégeait l'ingestion des doublons : il effaçait tout
menu absent du vault, donc un menu créé via l'API, sans erreur ni trace.

⚠️ **Le `slug` est la clé, pas le nom de fichier — deux fiches peuvent le déclarer
en double**, et l'upsert n'en garde qu'une. `read_recipes()` les départage sur la date
**déclarée** (`updated`/`created`) et expose `_duplicate_paths`, qu'`ingest.py` remonte en
warning. ⚠️ **Ne jamais départager au `_mtime`** ni à l'ordre du glob : sur le VPS le vault
est un mount rclone, le mtime date la *copie*, pas la donnée.

### Relier un repas à sa recette — deux marqueurs dans `meals:`

Chaque repas devient une ligne `menu_meal` (menu × jour × créneau) à l'ingestion.
L'appariement par titre échoue toujours — l'intitulé du menu, rédigé à la main,
diverge du titre de la fiche. D'où deux marqueurs par créneau :

| Marqueur | Effet |
|---|---|
| `<slot>_slug: <recipe-slug>` | **désigne** la fiche explicitement — court-circuite l'heuristique. La seule liaison qui ne redérive pas. Un slug inconnu est journalisé, jamais silencieux. |
| `<slot>_leftovers: true` | repas de **restes**, sans fiche PAR CONCEPTION — lui en donner une ferait racheter les ingrédients du repas recyclé. Rendu dans `meals_leftovers`, pas `meals_unmatched`. |

⚠️ **Une recette au menu doit avoir sa fiche `Recettes/*.md` AVANT le calcul des
courses** — l'app ne lit QUE les fiches. Les recettes de la semaine vivent
parfois dans le **panier** (`data/shopping_choices_*.json`, chaque article porte
son repas) et pas dans `Recettes/` : générer les fiches manquantes depuis le
panier, ingrédients ancrés sur l'acheté (jamais inventés).

## Compatibilité alimentaire — ne pas la vérifier à la main

```bash
curl -s https://cooking.srv759970.hstgr.cloud/api/menus/<slug>/compatibility
```

Croise **qui est réellement à table** et **ce que chacun ne peut pas manger** —
tout vient de la DB (cf. § Gotchas, Tablée). Ne jamais raisonner sur la grille
type « mardi midi, enfants à la cantine » : elle porte la mention *« hors
vacances scolaires »*, donc en août elle donne une réponse fausse avec l'aplomb
d'une règle écrite. L'agenda Google n'apporte que les exceptions, jamais la
trame — il ne suffit pas comme source.

## Commande vocale (STT + LLM)

Pipeline : MediaRecorder (front) → `POST /api/audio` → Deepgram prerecorded (STT) → Groq LLM (intent JSON) → exécution. Panneau `#mic-panel` affiche la transcription et l'action interprétée.

- **LLM intent** : Groq `qwen/qwen3.6-27b` (`reasoning_effort: "none"`, ~300 ms). Ollama cloud en fallback si `GROQ_API_KEY` absent
- **Credentials** : credstore systemd (`cooking-deepgram-key`, `cooking-ollama-key`, `groq-key` partagé avec bibliotheque), lues par `deploy/run-with-cred.sh`
- **MediaRecorder** exige Safari 14.5+ — le FAB micro est **masqué** sur Safari 12 (feature-detect). Le panneau vocal n'apparaît jamais sur l'iPad mini 2
- **Les intents sont déclarés dans le PROMPT** de `backend/stt.py`, pas dans une table — les lister : `grep -oP '^\d+\. \K\w+' backend/stt.py`. Un intent ajouté au prompt sans être câblé côté exécution échoue en silence

## Macros — la doctrine vient du vault, pas du code

`cooking_manager/nutrition.py` n'invente aucune donnée : il applique les règles
du **Coach Nutrition** (`Noyau/Coaches/Coach Nutrition/_coach.md`).

- **Règle 1 — pas d'hypothèse.** Un ingrédient non résolu ressort en
  `unresolved` **avec son motif**, jamais estimé au jugé ni omis.
- **Règle 2bis (erreur #25).** `kcal_reconstitué = P×4 + G×4 + L×9` ; au-delà de
  5 % d'écart, **montrer les deux chiffres**. Les fiches CIQUAL ont 5–15 %
  d'écart structurel (eau, cendres, fibres hors somme) — l'écart n'est pas un
  bug, le cacher en est un.
- **Trois sources hiérarchisées** : fiche `marques/` (étiquette vérifiée) >
  `shopping_product.nutrition` (étiquette scrapée du drive) > `generiques/`
  (ANSES CIQUAL). Jamais d'estimation implicite en quatrième position.

⚠️ **Le Coach Nutrition claude.ai est délibérément séparé de CM2** (§ Gotchas,
« deux garde-manger ») — mais sur demande **explicite** de Julien, Claude Code
peut l'**impersonner** dans cette session, en s'appuyant sur `_coach.md` (grille
kcal/macros par type de journée, règles 1/2bis/3) plutôt qu'en inventant des
cibles. Ne pas le faire par défaut ; croiser le stock via `pantry_item` (DB),
jamais `Garde-manger.md` vault seul, dont des postes se sont révélés faux au
2026-09-01.

⚠️ **Trois pièges de lecture, tous non détectables sans discipline explicite** :
la base sans mention « pour 100 g » est **ignorée**, pas supposée (3 dispositions
de tableau coexistent, transposée comprise — auditer via
`julien-audit-cooking-vault`) ; une fiche « Crues »/« Cuites » sans que la
recette ne nomme sa forme **ne tranche pas**, le parseur refuse plutôt que
deviner (facteur 3 en jeu) ; `coverage`/`conclusive` priment sur le total —
une somme sur la moitié des ingrédients n'est pas « les macros de la recette »,
et les unités-pièce ne convertissent pas sans poids unitaire.

⚠️ **Deux pièges d'implémentation** : la base aliments vit sur le mount rclone
(lecture lente) → `load_food_base_cached()` obligatoire, jamais relue par
requête ; `qty_min` arrive en `Decimal` (NUMERIC asyncpg), ne se multiplie pas
par un flottant — un test en `float` ne voit pas ce cas.

## Gotchas

- **Auchan Drive : une seule voie de connexion — le MCP VPS** (`mcp-vps-auchan`, port 3854, refs #60). Les modules `backend/auchan*.py` sont décommissionnés, contexte magasin compris (`grocery_find_stores`/`grocery_set_store`). La session Auchan du VPS est gérée par le seul **Cookie Health VPS**. HydraSpecter = outil de diagnostic, **pas** une voie de connexion
- **Tablée : 100 % DB, plus aucune lecture de `Presences.md` ni `Convives.md`** (refs #33). Tout vient de `load_referential_from_db()` (school_period, absence, stay) et `load_convives_from_db()` (`person`). Résolveur : `GET /api/attendance?day=&slot=`, `presence.py::attendees()`. `stay`+`stay_member` corrige F.30 : en location on cuisine sur place, donc les membres du séjour sont à table quelles que soient la trame et les absences. `ADULTS`/`CHILDREN`/`CUSTODY_REFERENCE_WEEK` ne sont plus qu'un **repli** sans `HouseholdConfig`. `convive` (legacy) et `person` coexistent ; `person` fait autorité. ⚠️ **`POST /api/seed` n'est idempotent que depuis le 2026-09-03** : son `DO UPDATE` réimposait `dislikes`/`forbidden` depuis ses constantes, donc il effaçait sans un mot les préférences saisies après coup. Ces listes ne sont désormais posées qu'à la CRÉATION — ne jamais les remettre dans le `DO UPDATE`. ⚠️ **`attendees()` annonce quatre niveaux (override > séjour > trame > absences) mais le sommet est INATTEIGNABLE** : rien n'écrit `meal_attendance`, donc l'override manuel n'arrive jamais, et le résolveur répond avec la trame sans le signaler. Même chose pour `stay.cooking` et `extra_headcount` : écrits ou exposés, lus par aucun calcul. Refs #73 — ne pas raisonner sur ces trois-là comme sur des données vivantes
- **Une photo qui n'est pas un fichier local est une photo en sursis.** `_scrape_photo()` reconstruit `photo_url` à chaque ingestion depuis un site tiers ; l'upsert doit rester `photo_url=COALESCE($24, recipe.photo_url)`, sans quoi **un scraping qui échoue efface la photo** sans erreur. La parade de fond est le fichier local `web/media/recipes/<slug>.jpg`, prioritaire et insensible au réseau. Générer les manquantes via **recipe-manager** (`POST /recipes/<slug>/generate-image`, port 8796), qui porte le prompt v1.1 — jamais un prompt improvisé, sinon le parc perd son unité visuelle. Récupérer avec `?inline=true` → `image_base64`, écrire dans `web/media/recipes/`, **committer**. Extension **`.jpg` obligatoire** : `ingest.py` ne scanne que celle-là, un `.png` déposé n'est jamais rattaché (refs #70)
- `httpx`/`selectolax`/`mcp` sont des dépendances déclarées dans `pyproject.toml` — un venv reconstruit à neuf (`pip install .`) est le test de vérité si ce fichier dérive
- Toute nouvelle colonne dans un CREATE TABLE doit aussi etre dans MIGRATIONS_SQL (`ALTER TABLE ADD COLUMN IF NOT EXISTS`) — le VPS a deja les tables, `CREATE TABLE IF NOT EXISTS` ne rajoute rien
- `menu_meal.position` est **1-based** en DB (`enumerate(meals, start=1)`) — tout consommateur JS doit faire `position - 1` pour indexer le tableau `menu.meals[]`
- Après un `rclone copy` vers Dropbox, le mount VPS (`/mnt/dropbox-full`) peut avoir un délai de propagation (~30 s) — relancer `POST /api/ingest` si une recette n'apparaît pas
- **La liste de courses n'est PAS un objet stocké — c'est un calcul.** `GET
  /api/menus/{slug}/shopping-list` la recalcule intégralement à chaque appel (menu × tablée ×
  garde-manger) ; le front la garde en RAM (`state.shopping`), rien en DB, rien en
  `localStorage`. Ce qui persiste, `shopping_session`/`shopping_product`, est un **compte rendu
  d'après coup** d'une commande drive — jamais un plan, et relié à aucun menu. Corollaire :
  aucune ligne n'a d'état, aucun tour ne se clôt, et rien ne dit **où** un article doit être
  acheté (`shopping_session.store` n'est rempli qu'après). Le modèle cible (tour borné,
  canal, réattribution, besoin résiduel) est dans `docs/conception/USE_CASES_COURSES.md` —
  le lire avant de toucher aux courses. Refs #67, #68
- `_pantry_from_db()` remplace `_load_pantry()` — le différentiel courses lit la DB, source de vérité pour l'app (le vault n'est qu'une source d'ingestion parmi d'autres ; `source != 'vault'` survit à la ré-ingestion — **donc aucune correction du vault ne les atteint jamais** : une ligne `receipt` est un événement d'achat daté, pas un état de stock, et reste `ok` indéfiniment, refs #69). ⚠️ **`Noyau/Cuisine/Garde-manger.md` est aussi lu/écrit par un système entièrement séparé** — le Coach Nutrition sur claude.ai, qui planifie les menus macro par macro et n'appelle jamais l'app ni sa DB. Les deux garde-manger ne sont **jamais synchronisés** et peuvent diverger sans alerte (constaté 2026-09-01 : 6 articles listés « ok » dans le vault n'existaient plus réellement)
- **Cuissons, cuisines, textures et techniques d'accommodation viennent de l'ONTOLOGIE, jamais d'une table écrite dans le code.** Source : `data/ontology/cooking-vocabulary.yaml` (ce repo) → `ontology-manager` (`kind: cooking`) → artefact épinglé `cooking_manager/cooking-vocabulary.json`. Modifier le YAML, régénérer (`python -m ontology_manager.cli generate --ontology cooking-vocabulary`), recopier l'artefact. Deux tests refusent qu'une règle cite une clé absente du vocabulaire ou déclarée sans synonyme — donc indétectable. ⚠️ **Le générateur a un jeu de champs FIXE** (`ontology_manager/cooking.py`) : un champ ajouté au YAML n'atteint pas l'artefact tant qu'il n'y est pas propagé, et le consommateur lit alors une valeur vide **sans erreur** — un tri par `observed_in` aurait compté zéro partout en paraissant marcher. Ajouter un champ = toucher les deux dépôts, plus un test qui prouve qu'il survit à la génération
- **Une cuisson préparatoire n'est pas la cuisson du plat.** « Faites dorer » ouvre presque tout mijoté : sans la table `dominates` du vocabulaire (`stew`/`slow-cooked` absorbent `pan-fried`/`pan-seared`/`stir-fry`, consommée par `drop_dominated()`), `pan-fried` pesait autant que `stew` et faisait gagner une dorade grillée dans une cocotte. N'y inscrire **que ce qui a été observé** — une dominance plausible mais non mesurée est le défaut reproché à `separate_dish`
- `cooking_mcp.py` importe `from fastmcp import FastMCP` (pas `from mcp.server.fastmcp`) — seul le package `fastmcp` (v3.4+) expose `host`/`port`/`allowed_hosts` dans `run()`. Le package `mcp` v2 a un `FastMCP.run()` minimaliste
- Tout MCP VPS derrière nginx avec `Host $host` doit passer `allowed_hosts=[<domaine>]` à `mcp.run()`, sinon Starlette retourne 421
- ⚠️ **TOUT terme alimentaire se déclare au SINGULIER** — régimes (`DIETS`), `dislikes`, `forbidden`, `diet_exceptions`. `_contains_term()` compare en mots entiers et tolère la flexion « s »/« x » **sur chaque mot**, mais uniquement du singulier VERS le pluriel : « lardon » rencontre « lardons », « lardons » ne rencontre PAS « lardon ». Le contraire ne produit aucune erreur — juste un plat déclaré compatible. C'est ce qui rendait 82 formes plurielles muettes jusqu'au 2026-09-03 (`lardons`, `veaux`, `steaks`, `jambons`), soit la forme la plus courante d'une ligne d'ingrédient. Les frontières de mot, elles, sont **volontaires** : « maïs » ne doit pas matcher « maison », ni « citron » « citronnelle »
- **Un régime n'est pas un absolu : `person.diet_exceptions`** — Clémence est pescétarienne ET mange du boudin et les quenelles de veau. Une exception dispense **la ligne** qui porte l'expression, jamais le terme entier — sans quoi lever les quenelles de veau laisserait passer le rôti de veau. Ne pas confondre les trois axes : `forbidden` = ce qui ne se discute pas · `dislikes` = aversion (les cuissons d'œufs en sont) · `diet_exceptions` = ce que le régime interdit mais que la personne mange
- **Le régime refuse bien plus large que le moteur ne sait réparer** — `convives.py` bloque sur les termes de `DIETS`, `RULES_BY_DIET` n'en couvre qu'une minorité (compter : `python -c "from cooking_manager.convives import DIETS; from cooking_manager.substitutions import find_substitution; print(sum(1 for t in DIETS['pescetarian'] if find_substitution(f'200 g de {t}') is None), '/', len(DIETS['pescetarian']))"`). Un `repairs` vide ne veut donc PAS dire « rien à réparer » : lire `unrepaired`. Une protéine sans règle nommée reçoit un **repli** tiré du catalogue de cibles selon la cuisson détectée (`fallback: true`, confiance 0.4) ; sans cuisson détectée, rien n'est deviné. ⚠️ **Une règle NOMMÉE ne s'ajoute jamais sans observation** — elle porte une raison affichée à l'utilisateur, et une raison inventée ment avec l'aplomb d'une règle mesurée ; c'est précisément ce que le repli, qui se déclare comme tel, permet d'éviter
- **Une règle de `substitutions.py` qui déclare des `cuisines` doit être bornée par `rule_applies()`** — `score_rule()` bonifie un match de cuisine mais ne pénalise pas son absence, donc une priorité de base élevée suffit à faire gagner une règle hors de son contexte (une règle ouest-africaine s'appliquait à tout mijoté de poulet, y compris un coq au vin). Toute nouvelle règle à forte priorité doit être testée sur un plat d'une AUTRE cuisine

## Skills liées

- `julien-audit-cooking-vault` — **owner** — audite les données que ce repo ingère
  (`Noyau/Cuisine/` + la base aliments du Coach Nutrition). À lancer **avant** une
  génération de courses : c'est là que les défauts de données coûtent de l'argent.
- `cooking-manager-weekly-pipeline` — **owner** — le pipeline hebdomadaire complet
  (vault → menu → quantités → compatibilités → courses). Toute modification de
  l'ingestion ou du différentiel de courses le périme.
- `cooking-manager-auchan-drive` — **gros-consommateur** — pilote le panier Auchan
  depuis les courses produites ici.

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
