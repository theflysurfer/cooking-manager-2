# HANDOFF (jetable) — « recipe-manager est-il un étage de trop ? » + état voie (b)

> Doc **jetable** pour le prochain LLM. À supprimer une fois la décision prise et un ADR écrit.
> Écrit le 2026-09-11. Contexte : session précédente trop grosse, on passe la main.
> Reprendre avec **superpowers** (`brainstorming` puis `writing-plans`), pas en codant direct.

---

## Question de Julien (vraie question, pas rhétorique)

> « recipe-manager est un étage de trop, il devrait être un **module de cooking-manager**
> plutôt qu'un service séparé. Aide-moi à comprendre / critiquer / amender / compléter. »

## Ce qu'il faut savoir AVANT d'y répondre (découvertes de cette session)

1. **recipe-manager a été EXTRAIT de CM2 exprès** (registry : « extrait de — schema recipe +
   vault ingestion + ingredient parser extraits de CM2 »). Sessions du 2026-08-08
   (`recipe-manager-phase1-phase2`, `deploy-recipe-manager-absorb-parser`) + **ADR 0005**
   du repo `cooking-manager-2-handoff-20260901` (« l'import de recette est une façade vers
   recipe-manager »). La proposition de Julien **inverse** cette extraction — donc il faut
   comprendre POURQUOI elle a été faite avant de la défaire.
2. **Motif de l'extraction = un DEUXIÈME consommateur.** Registry : recipe-manager est le
   « modèle canonique de recettes partagé, consommé par **Cooking Manager 2** (colocataire DB)
   ET **Waaker** (via API) ». nginx expose `/api/recipes-shared/`.
3. **Deps lourdes/occasionnelles** : `llm_backend: gemini` (génération d'images
   `POST /recipes/{slug}/generate-image`) + **ollama-cloud** pour le parsing d'URL
   (`LLM_MODEL`, défaut `gemma3:cloud`). Plus vraisemblablement OCR/scraping pour l'import photo.
   CM2 vise l'iPad mini 2 en cuisine : API légère, toujours allumée, latence sensible.
4. recipe-manager porte : import photo/URL, workflow de **drafts** (table drafts probable, à lui),
   parsing, génération d'images. CM2 y accède via `_rm_request` (façade `/api/recipes/import/*`,
   `/parse-url`, `/commit`). Le `commit` **écrit un `.md` dans le vault** puis relance l'ingest CM2.

## Critique / cadrage (le cœur de l'aide)

**Ne pas confondre DEUX axes** — Julien dit « module vs service » mais ce sont deux décisions
distinctes qu'on peut prendre séparément :

- **Axe A — le code/repo** : un repo séparé vs un package dans le monorepo CM2.
- **Axe B — le déploiement** : un service systemd séparé (8796) vs plié dans le process CM2 (8795).

On peut collapser l'un sans l'autre. Trois options concrètes :

| Option | Repo | Service | Effet |
|---|---|---|---|
| **(a) Fusion totale** | module de CM2 | 1 seul process | « étage de trop » supprimé. **Mais** Waaker devient dépendant de CM2 (l'app cuisine) pour son modèle de recettes, et les deps LLM/OCR entrent dans le runtime iPad-critique. |
| **(b) Monorepo, 2 déployables** | package partagé dans CM2 | 2 process (kitchen API + recipe API) | partage le code (ex. `write_recipe` qu'on vient d'extraire) sans coupler les runtimes. Compromis. |
| **(c) Statu quo, mais finir 0010** | séparé | séparé | ne touche pas à l'étage ; règle juste le round-trip `.md` (voie b, cf. ci-dessous). |

**La question pivot, à trancher AVANT tout** : **Waaker est-il réel/imminent, ou différé ?**
- Si Waaker consomme vraiment recipe-manager → l'extraction était juste, un service partagé à
  deux consommateurs se défend. Fusionner dans CM2 = mettre l'app cuisine au centre d'un graphe
  de dépendances qu'elle ne devrait pas porter. **Option (a) déconseillée.**
- Si Waaker est vaporware/lointain → recipe-manager est de fait un service **à un seul
  consommateur** = extraction prématurée, l'instinct de Julien est bon. **(a) ou (b) légitimes.**

**Argument transverse** (vrai dans tous les cas) : les deps LLM/OCR/scraping sont **bursty et
lourdes** ; les isoler du process cuisine (toujours allumé, iPad, latence) a de la valeur —
ce qui pousse vers **(b)** plutôt que **(a)** même si on veut un seul repo.

## À VÉRIFIER par le prochain LLM (ne pas supposer)

- [ ] **Waaker** : statut réel (registry `theflysurfer/waaker`), consomme-t-il déjà
      `/api/recipes-shared/` ou est-ce « consommera » (futur) ? → détermine (a) vs (b)/(c).
- [ ] Lire **ADR 0005** (`cooking-manager-2-handoff-20260901/docs/decisions/0005-*`) et les 2
      diaries du 2026-08-08 : le POURQUOI de l'extraction, pour ne pas le re-piétiner.
- [ ] Deps réelles de recipe-manager (`2026.08 Recipe Manager/pyproject.toml`) : quel poids
      entrerait dans le runtime CM2 en cas de fusion (a).
- [ ] Tables propres à recipe-manager (drafts, images ?) vs tables partagées (recipe/*).
- [ ] `deep-research#51` / `recipe-manager#4` : doublon d'extraction JSON-LD — frontière
      recommandée pas encore actée (peut influencer où vit le parsing).

## État de la voie (b) 0010 — lié, à finir dans la même réflexion

Cette session a livré la **Phase 1** (cf. **ADR 0020**) : chemin d'écriture recette **DB-natif**
sur CM2 (`POST/PUT/DELETE /api/recipes` + MCP `recipe_upsert`/`menu_upsert`/`*_delete`),
déployé + testé (373 tests). **Phase 2 en pause** (décision Julien).

⚠️ **Dual-writer temporaire** : une recette écrite via l'API dont un `.md` de même slug existe
est **écrasée au prochain ingest**. C'est le piège que 0010 voulait tuer, ré-ouvert le temps
de la pause. (Détail + TODO Phase 2 dans ADR 0020.)

**Le lien entre les deux sujets** : « qui écrit les recettes » (Phase 2) et « recipe-manager
étage de trop » sont la **même** décision d'architecture. Le `commit` de recipe-manager écrit
du `.md` ; le retrait du vault (0010) exige de changer ça ; et si on fusionne (a/b), le commit
appelle `write_recipe` en direct. **Traiter les deux ensemble**, pas séparément.

## Reco de démarrage pour le prochain LLM

1. `brainstorming` (superpowers) sur la question pivot Waaker + les 3 options.
2. Lire ADR 0005 + 0010 + 0020 + diaries 2026-08-08 **avant** toute proposition.
3. `writing-plans` pour un plan Phase 2 + (fusion ou non), avec l'équivalence DB↔vault comme gate.
4. Écrire l'ADR qui tranche (superséder/compléter 0005 et 0010).
5. Ne rien retirer du vault ni toucher recipe-manager sans que l'équivalence soit prouvée et
   Waaker tranché.

## Point d'hygiène mineur

`ruff` + `pytest` ont été installés dans le **venv du VPS** (`/opt/cooking-manager-2/.venv`)
pour faire tourner les gates côté serveur — il n'existe **aucun venv de dev local** (python
masqué par le stub Windows Store). À trancher : est-ce le lieu voulu des gates, ou monter un
venv de dev propre ?
