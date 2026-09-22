---
title: Référentiel aliment & produit — phase 3, l'aliment devient la clé d'appariement
axis: conception
proof_level: plan
upstream: [PLAN_referentiel-aliment-produit-phase2.md, SPEC_referentiel-aliment-produit.md]
downstream: []
status: à exécuter
date: 2026-09-22
adr: [0031, 0032]
issues: [94, 101, 102, 109, 117, 118, 120]
---

# Référentiel aliment & produit — phase 3

> La phase 2 a fait basculer les macros du vault vers la base et a laissé cinq chantiers ouverts.
> Deux d'entre eux — l'identité de `pantry_item` (#118) et les alias d'aliment (#117) — sont la
> cause mesurée de la panne du 2026-09-21. Cette phase les ferme, et ouvre le sens inverse :
> du stock vers les recettes.

## Le problème, mesuré le 2026-09-22

La commande `1f900f71` du 20/09 portait 46 lignes ; 41 sont entrées au garde-manger le 21/09.
Confrontées aux 104 ingrédients distincts du menu `2026-09-21_semaine-aubagne-enfants` :

| Cas | Compte | Exemple |
|---|---|---|
| Apparie exactement | 12 | `mozzarella rapee` |
| Même aliment, n'apparie pas | 14 | `auchan pois chiche 530g` ≠ `pois chiche` |
| Aucun besoin déclaré | 15 | `melon charentai`, `cottage cheese` |

Un cas ne cède à aucune règle lexicale : `quaker cruesli cereale au chocolat noir 900g` contre la
clé récurrente `céréales petit-déjeuner`, **zéro mot en commun**.

`matching.py:108` exige que le nom le plus court ouvre le plus long ; `pantry.py:108` rend `None`.
Aucun des deux ne lève quoi que ce soit. Cinq lignes se sont par ailleurs perdues entre la commande
(46) et le stock (41), sans qu'aucune trace ne permette de dire lesquelles :
aucune `shopping_session` n'a été créée.

## L'ordre, et pourquoi il ne s'inverse pas

```
1. Fusion recipe-manager      (ADR 0031) — donne recipe_ingredient à CM2
2. Colonne food_key           (ADR 0032) — impossible avant 1 sans table de liaison
3. Moteur de rapprochement                — produit les propositions
4. Rattrapage groupé                      — consomme les propositions
5. GET /api/pantry/cookable               — n'a de sens qu'après 4
```

Inverser 1 et 2 impose une table de liaison `ingredient_food` qu'on jetterait à l'étape 1, soit la
même migration faite deux fois.

---

## Étape 1 — Fusion de recipe-manager

**Livrable** : un process, port 8795. `recipe-manager.service` arrêté, dépôt archivé.

1. Déplacer les cinq `CREATE TABLE` (`recipe`, `recipe_ingredient`, `recipe_step`,
   `recipe_execution`, `import_draft`) de `recipe_manager/db.py` vers `backend/db.py`, en
   `SCHEMA_SQL`. Retirer l'avertissement de colocation de `backend/db.py:7-8`.
2. Porter les quatre routes propres : `/api/recipes/parse`, `/api/recipes/parse-html`,
   `/api/recipes/import/page`, `/api/recipes/{slug}/generate-image`. Conserver la forme de payload
   de `ParseHtmlRequest` — `{ html, url, enable_llm }` — parce que Waaker l'envoie déjà.
3. Supprimer `RECIPE_MANAGER_URL` et les façades `_rm_request` de `backend/app.py:3109-3180`.
4. `pyproject.toml` : ajouter `pillow` et `python-multipart`. Rien d'autre.
5. Rendre `POST /api/recipes/import/page` asynchrone — `202` + `task_id`, plus
   `GET /api/recipes/import/tasks/{id}`. La durée du chemin `pillow` n'est pas mesurée ; c'est la
   seule raison de l'isoler.
6. `deploy/cooking-manager.service` : retirer `Requires=` et `After=recipe-manager.service`.
   `deploy/cooking-manager.nginx.conf` : retirer l'`include` du snippet.
7. Waaker, `src/lib/parsers.ts:1` : `8796` → `8795/api/recipes`. Le même jour.
8. `systemctl disable --now recipe-manager`. Retirer le snippet nginx et le credential Gemini de
   recipe-manager, reposer la clé côté CM2.
9. Supprimer les 118 `.md` du vault, y compris forcé côté cloud Dropbox — les suppressions locales
   ne remontent pas.
10. `gh repo archive theflysurfer/recipe-manager`. Registre : `active` → `archived`, et retirer de
    `relations.json` la relation « fournit à Waaker (modèle de recettes partagé) ».

**Gates** : `ruff` · `pyright` · `pytest` verts · `check_comments.py . --ci` · `curl` sur les quatre
routes portées depuis le VPS · un `POST /parse-html` émis depuis Waaker qui rend une recette.

---

## Étape 2 — La colonne d'aliment

**Livrable** : `food_key` sur `pantry_item` et `recipe_ingredient`, et un compteur de non-rattachés.

1. `SCHEMA_SQL` **et** `MIGRATIONS_SQL` — le VPS a déjà les tables, une colonne ajoutée au seul
   `CREATE TABLE` n'y arrive jamais :
   ```sql
   ALTER TABLE pantry_item       ADD COLUMN IF NOT EXISTS food_key TEXT REFERENCES food(key) ON DELETE SET NULL;
   ALTER TABLE recipe_ingredient ADD COLUMN IF NOT EXISTS food_key TEXT REFERENCES food(key) ON DELETE SET NULL;
   ```
   `ON DELETE SET NULL`, jamais `CASCADE` : supprimer un aliment ne doit pas effacer une ligne de
   stock ni un ingrédient. Leçon des sept alias emportés le 2026-09-07.
2. Les index ne vivent que dans la migration — `SCHEMA_SQL` s'exécute avant :
   ```sql
   CREATE INDEX IF NOT EXISTS pantry_item_food_idx       ON pantry_item(food_key);
   CREATE INDEX IF NOT EXISTS recipe_ingredient_food_idx ON recipe_ingredient(food_key);
   ```
3. `shopping_session.status` : `cart` | `ordered` | `abandoned`, défaut `cart`. Les deux sessions
   existantes passent à `ordered`.
4. Exposer le compteur sur `/api/pantry`, `/api/menus/{slug}/shopping-list` et `cookable` :
   `{"linked": n, "unlinked": n}`. Il se lit **avant** toute ligne, comme `slots_uncomposed` et
   `preferences_unmeasurable`.

**Gate** : un test qui échoue si `unlinked` est absent d'une des trois réponses. Un compteur qu'on
peut oublier d'afficher n'est pas un compteur.

---

## Étape 3 — Le moteur de rapprochement

**Livrable** : `cooking_manager/linking.py`, pur, sans I/O réseau, et une file d'arbitrage.

Cascade, dans cet ordre, chaque étage rendant des **candidats** et jamais une décision :

| Étage | Entrée | Sortie |
|---|---|---|
| 1. exact | `name_normalized` | 0 ou 1 candidat |
| 2. trigramme | `pg_trgm similarity > 0.45` | n candidats, scorés |
| 3. jugement | 0 ou ≥ 2 candidats | Claude, API HTTP Ollama cloud |
| 4. refus | Claude non sûr | `food_key NULL`, compté, nommé |

Contrat de l'étage 3 : la sortie est bornée à une clé du référentiel ou `null`. Claude ne crée
jamais un aliment. Le prompt porte les candidats de l'étage 2 et la consigne de refuser.

Une forme est le défaut : `pave de saumon` devient `food_form(food_key='saumon', label='pavé')`.
Un aliment neuf est une décision explicite, tracée.

Un arbitrage rendu s'écrit dans `pantry_alias` et ne se redemande jamais.

Routes :
```
GET  /api/pantry/pending-links          la file, groupée par aliment candidat
POST /api/pantry/links                  trancher, par lot
```
Deux portes sur la même file : Claude Code pendant la course, `web/` à tête reposée. Ce qui est
tranché d'un côté disparaît de l'autre.

`POST /api/shopping/validate-cart` rend `ok: false` tant qu'une ligne n'est pas tranchée, et nomme
celles qui manquent. Ce gate s'**empile** sur celui de l'ADR 0028 : arbitrage, puis `persist-cart`,
puis diff de réconciliation.

Le ménager et le non-alimentaire se déclarent `recurrent` dans `shopping_preference` et sortent de
la file sans compter comme un trou.

**Gates** : un test par étage · un test qui prouve que l'étage 4 sait échouer, c'est-à-dire qu'une
entrée sans candidat rend `NULL` et non le premier venu · un test qui prouve qu'un `composite` n'est
jamais rattaché (ADR 0016, ratchet existant).

---

## Étape 4 — Le rattrapage

**Livrable** : les 460 lignes tranchées, en une passe.

```
330 pantry_item  (dont 221 source='vault')
130 product sans food_key (sur 170)
    les ingrédients de recette du référentiel
```

L'écran groupe par aliment candidat : les libellés qui désignent la même chose arrivent ensemble.
Environ 80 décisions pour 460 lignes.

```
SAUMON (7 libellés)
  pave de saumon · filet de saumon · saumon fume · pave de saumon sauvage …
  [ même aliment ]   [ scinder ]
```

**Gate** : `unlinked` mesuré avant et après, et publié dans le diary. Pas d'objectif chiffré écrit
ici — il se mesure, il ne se prédit pas.

---

## Étape 5 — Du stock vers les recettes

**Livrable** : `GET /api/pantry/cookable`.

```json
{
  "linked": 298, "unlinked": 32,
  "have": [{"food": "brocoli", "qty": "900 g", "entered_at": "2026-09-11", "urgency": "perishable"}],
  "recipes": [{"slug": "...", "uses": ["brocoli", "ail"], "missing": ["creme"], "coverage": 0.66}],
  "unusable": [{"food": "salade batavia", "reason": "aucune recette du référentiel ne la nomme"}]
}
```

`unlinked` se lit **avant** `have` : une liste vide doit dire « je n'ai rien su rattacher », jamais
« tu n'as rien ».

`unusable` est le champ qui répond à la question du 21/09 : ce qui est en stock et qu'aucune recette
ne sait consommer.

---

## Ce qui reste hors de cette phase

| Sujet | Où |
|---|---|
| Décrément du stock au repas servi | les déductions se **proposent** ; l'automatisme n'est pas décidé |
| Revue trimestrielle du rayon sec | un rappel, pas un effet sur le calcul — risque assumé, ADR 0032 |
| Familles de protéine en ontologie | #109, inchangé |
| Macros multi-formes d'un **produit** | #112, inchangé |

## Le critère de réparation

`tests/test_ratchet_rattachement.py` rejoue les **41 libellés réels du 2026-09-21**. Chacun finit
dans exactement un état : rattaché à un aliment, déclaré hors menu, ou nommé en attente
d'arbitrage. **Aucun en silence.** Douze y parviennent aujourd'hui.

Le test rejoint les quatre métriques ratchet existantes : une régression casse `pytest` et bloque le
ship.
