# Cooking Manager 2

Web app pour parcourir et filtrer les recettes familiales depuis le vault Obsidian.

## Stack

- **Backend** : FastAPI + asyncpg (PostgreSQL)
- **Frontend** : vanilla JS, **zéro build** — fichiers statiques servis par FastAPI
- **DB** : `postgresql-shared` (Docker) → database `cooking_manager`, user `cooking`
- **Deploy** : systemd `cooking-manager.service` + nginx sur srv759970, port 8795

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
  auchan.py        # client Auchan Drive (reverse-engineered)
  auchan_mcp.py    # serveur FastMCP (stdio)
web/               # Front : index.html + style.css + app.js (+ media/recipes/)
tests/             # unitaires · gate compat iOS 12 · e2e (opt-in)
data/              # sessions de courses + photo-prompt.md (versionné)
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
| `Menus/*.md` | **le bloc `meals:` du frontmatter** fait foi, pas les tableaux du corps | `menu.meals` (JSONB) |
| `Convives.md` | régimes, interdits, cuissons d'œufs refusées, aversions | `convive` |
| `Presences.md` | vacances scolaires, absences, exceptions | lu à la volée (pas de table) |

⚠️ **`menu.slug` est la clé naturelle.** Sans elle, l'ingestion se protégeait des
doublons par un `DELETE FROM menu` qui effaçait tout menu absent du vault — un
menu créé via l'API disparaissait à la première ingestion de recettes, sans
erreur ni trace. Ne jamais réintroduire ce DELETE.

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

## Auchan Drive API

Client reverse-engineered (`backend/auchan.py`). Auth : Bearer JWT Keycloak + `x-gravitee-api-key`. Catalogue : SSR scraping (pas d'API produit). Cart : `POST api.auchan.fr/checkout/v1/carts/{cartId}/items` (add/update/remove via `desiredQuantity`). Remove nécessite l'`id` interne (GET cart d'abord). MCP local : `python -m backend.auchan_mcp` (stdio) — expose aussi `grocery_persist_cart`, qui persiste et enrichit un panier via `POST /api/shopping/persist-cart`.

⚠️ Le connecteur **claude.ai** `Auchan Drive` (hébergé, pas ce repo) n'expose que l'ajout au panier — `quantity=0` pour supprimer y échoue systématiquement en 500 (refs #13). Toute suppression/mise à jour de quantité doit passer par `backend/auchan_mcp.py` ou un appel direct à `AuchanClient`.

## Persistance + enrichissement nutritionnel

`POST /api/shopping/persist-cart` persiste chaque article dans `shopping_product` et l'enrichit en direct (nutrition, nutriscore, ingrédients, allergènes, caractéristiques, photo, prix/kg) via `backend/auchan.py::find_product_detail()` — pont entre l'UUID interne du panier et l'ID public catalogue (recherche par nom, puis scrape de la fiche produit). Séquentiel, un item peut prendre plusieurs secondes — le timeout nginx `/api/` est à 300s pour cette raison (`deploy/cooking-manager.nginx.conf`).

## Gotchas

- Le token Auchan expire fréquemment — refresh via navigateur uniquement
- `consentId` requis comme query param sur tous les appels cart
- La recherche SSR nécessite le cookie `auchan_store_reference=874` (Aubagne)
- Remove cart : l'`id` interne (UUID) ≠ `productId` — toujours GET cart d'abord
- `httpx`/`selectolax`/`mcp` sont des dépendances déclarées dans `pyproject.toml` — un venv reconstruit à neuf (`pip install .`) est le test de vérité si ce fichier dérive

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
