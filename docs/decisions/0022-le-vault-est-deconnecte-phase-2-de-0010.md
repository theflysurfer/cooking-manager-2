# 0022 — Le vault est déconnecté — Phase 2 de 0010

- **Statut** : accepté
- **Date** : 2026-09-16
- **Supersède** : ADR 0020 (Phase 2 « reste à faire » → fait)
- **Suit** : ADR 0010 (le vault cuisine est décommissionné), ADR 0017 (garde-manger coupé)

## Contexte

L'ADR 0010 a décidé « la DB est la seule source de vérité ». L'ADR 0020 a livré
Phase 1 (chemin d'écriture DB-natif) mais différé Phase 2 (couper les lectures
vault) parce que recipe-manager (8796) écrivait encore des `.md` via rclone.

Cinq connexions vault restaient vivantes :
1. `read_recipes()` — recettes `.md` lues à chaque `POST /api/ingest`
2. `read_menus()` — menus `.md` lus à chaque ingest
3. `read_convives()` + `parse_convives()` — `Convives.md` → tables `convive`/`person`
4. recipe-manager `commit` — écrivait `.md` dans le vault puis rappelait l'ingest CM2
5. MCP `vault_ingest` — déclencheur de l'ingest

## Décision

**Toutes les lectures vault sont supprimées.** Deux repos touchés :

### CM2 (cooking-manager-2)

- `ingest()` supprimée, remplacée par `relink_meals()` (re-résout les liens
  menu_meal → recipe sans lire le filesystem).
- `POST /api/ingest` ne lit plus le vault : appelle `relink_meals()`.
- `commit_import_draft` ne relance plus l'ingest vault : vérifie directement
  en DB que la recette est visible.
- MCP `vault_ingest` → `relink_meals`.
- `vault.py`, `build.py`, `compiler.py` supprimés (code mort).
- `test_vault.py` supprimé.
- `VAULT_ROOT` retiré de `config.py`.

### recipe-manager (8796)

- `commit` écrit directement dans les tables `recipe`, `recipe_ingredient`,
  `recipe_step` au lieu de poser un `.md` + rclone.
- `POST /ingest` renvoie un compteur depuis la DB, ne lit plus le vault.
- `vault.py`, `VAULT_ROOT`, `VAULT_REMOTE`, `IMPORT_STAGING_DIR` deviennent
  du code mort (non supprimés dans cette session — `vault.py` reste pour la
  fonction `read_recipes` non appelée).

### Ce qui ne change pas

- `food_import.py` lit `aliments-vérifiés/*.md` — c'est le **référentiel
  aliment**, pas le vault cuisine. Hors scope.
- `write_recipe()`, `write_menu()`, `_link_meals()` survivent comme writers
  DB réutilisables.
- Les tables `person` font foi pour les profils alimentaires. `Convives.md`
  reste dans le vault Obsidian comme documentation pour le Coach Nutrition
  de claude.ai mais n'est plus ingéré.

## Conséquences

- Le flux `rclone copy` → mount → `POST /api/ingest` avec son délai de 30 s
  disparaît entièrement.
- Le dual-writer temporaire de l'ADR 0020 est résolu : plus de `.md` qui
  écrase une écriture API.
- `Convives.md` porte des données (poing, format repas, substituts saveurs,
  lignage) non encore migrées en DB → issues créées.

## Écarté

- **Migrer tout le contenu de Convives.md en DB avant de couper.** Trop large
  pour cette session, et les données manquantes (poing, substituts) ne sont pas
  utilisées par le code CM2 aujourd'hui.
- **Supprimer vault.py de recipe-manager.** Risque de casser un import non
  identifié dans un script tiers ; à nettoyer séparément.
