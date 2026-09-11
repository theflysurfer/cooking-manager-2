# 0020 — Les recettes gagnent un chemin d'écriture DB-natif ; la bascule 0010 reste à finir

- **Statut** : accepté
- **Date** : 2026-09-11
- **Porte** : ADR 0010 (voie b, sous-projet recettes/menus — en cours)
- **Issues** : lié #69

## Contexte

L'ADR 0010 a décidé « la DB est la seule source de vérité, le vault cuisine est
décommissionné », en cinq sous-projets. Le sous-projet **recettes/menus** n'était
pas commencé : le seul chemin d'écriture d'une recette restait « éditer un `.md`
→ `POST /api/ingest` ». Julien a tranché pour finir la bascule côté recettes
(**voie b** : DB seule source, retrait du vault).

Découverte en cours de route : l'import photo/URL d'une recette passe par
**recipe-manager (8796)**, dont le `commit` **écrit un `.md` dans le vault** puis
relance l'ingest CM2. Retirer l'ingest sans changer recipe-manager casserait
l'import.

## Décision

1. **CM2 expose un chemin d'écriture DB-natif** : `POST/PUT/DELETE /api/recipes`,
   réutilisant la logique par-recette de l'ingest (`write_recipe`/`write_menu`
   extraits). Outils MCP `recipe_upsert`, `recipe_delete`, `menu_upsert`,
   `menu_delete`. `create_menu` relie désormais les `menu_meal` (l'ingest était le
   seul à le faire).
2. **Le retrait du vault est différé.** Phase 1 seule est livrée. `vault_ingest`,
   la lecture vault de `POST /api/ingest`, `read_recipes/menus/convives` et le gel
   des dossiers Cuisine ne sont **pas** touchés. Le vault **reste la source** des
   recettes et des menus en attendant.

## Conséquences

- ⚠️ **Dual-writer temporaire réintroduit** — exactement le motif que 0010 voulait
  supprimer, ré-ouvert le temps de la pause. Une recette écrite via l'API/MCP dont
  un `.md` de **même slug** existe dans le vault est **écrasée au prochain ingest**.
  Tant que la Phase 2 n'est pas faite : ne pas se fier à une écriture DB pour un
  slug qui a une fiche vault — l'éditer dans le `.md`, ou finir la bascule.
- Une recette écrite via l'API **sans** `.md` survit à l'ingest (upsert seul, pas
  de purge des recettes absentes du vault) mais reste **invisible dans Obsidian**.
- Aucun venv de dev local (python masqué par le stub Windows Store) : `ruff` et
  `pytest` ont été ajoutés au venv du VPS pour faire tourner les gates côté serveur.
  Lieu à confirmer.

## Reste à faire (Phase 2, prochaine session)

- Trancher : le `commit` de recipe-manager **appelle `POST /api/recipes`** (couture
  nette, CM2 seul écrivain) **ou** écrit les lignes en direct (tables partagées).
- Retirer `vault_ingest` (MCP), la lecture vault de `POST /api/ingest`,
  `read_recipes/menus/convives`.
- Geler/archiver `Noyau/Cuisine/{Recettes,Menus,Convives.md}`.
- Superséder la partie recettes/menus de l'ADR 0010 (sous-projet fait).
- MàJ `CLAUDE.md` (section « Vault → base ») + skills `julien-cooking-manager-weekly-prep`
  et `julien-cooking-donnees`.

## Écarté

- **Finir la Phase 2 tout de suite.** Demande un changement cross-repo
  (recipe-manager) et le gel du vault Obsidian de Julien. Arrêté sur sa décision
  explicite « pause, Phase 1 suffit pour l'instant » (2026-09-11).
