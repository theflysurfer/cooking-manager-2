---
title: Cas d'usage — Acquisition et réparation de recettes
axis: usage
proof_level: measured
upstream: [MOMENTS.md, ANALYSE_import-livre-cuisine.md, CORPUS_ACCOMMODATIONS.md, CORPUS_WEB_JSONLD.md]
downstream: [julien-test-case-design, TEST_NOMENCLATURE.md]
status: draft
date: 2026-09-02
---

# Cas d'usage — Acquisition et réparation de recettes

> **Le constat fondateur.** La base porte 56 recettes (`SELECT count(*) FROM recipe`),
> dont une vingtaine de plats compatibles — et le menu de la semaine du 2026-09-01 n'en
> utilisait **aucune**. Deux plats « inventés » par le Coach Nutrition y existaient déjà
> en fiche. Le répertoire est invisible à qui compose le menu (issue #72).
>
> Le problème n'est donc pas seulement d'**acquérir** des recettes. C'est que celles
> qu'on a ne servent pas. Ce document couvre les deux : les faire entrer, et les faire
> ressortir.

Légende couverture : **M** = modélisé · **P** = partiel · **A** = absent

⚠️ **Numérotation.** `TEST_NOMENCLATURE.md` catalogue jusqu'à SC-24, mais
`USE_CASES_TABLEE.md` occupe déjà **SC-25 à SC-32** sans que le catalogue l'enregistre.
Ce document reprend donc à **SC-33**. Le catalogue est en retard sur deux documents — à
resynchroniser.

## Ce qui existe aujourd'hui

| Brique | Rôle réel | Où |
|---|---|---|
| `POST /api/recipes/import` | page de livre photographiée → **proxy vers recipe-manager** | `backend/app.py:2374` |
| `GET/PATCH/DELETE /api/recipes/import/drafts[/{id}]` | réviser un **brouillon** avant qu'il devienne une fiche | `backend/app.py:2384-2402` |
| `POST …/drafts/{id}/commit` | écrit la fiche dans le vault, puis tente de la rendre visible | `backend/app.py:2405` |
| `POST /api/ingest` | vault → DB | `backend/app.py:1071` |
| `GET /api/recipes/{slug}/compatibility` | conflits + `context` + `repairs` | `backend/app.py:343` |
| `POST /parse-url` · `POST /parse-html` | **URL → recette, cascade 3 tiers** (JSON-LD → heuristique → LLM) | **recipe-manager**, `url_parser/parser.py` |
| `fetch_structured_recipe()` | URL → recette (JSON-LD + repli navigateur) — **doublon** du précédent | **deep-research**, `lifestyle/recipe_structured.py` |
| `_scrape_photo()` / `web/media/recipes/<slug>.jpg` | photo : scraping fragile vs fichier local | `backend/ingest.py` |

**Le pattern déjà établi, et il est bon : l'acquisition passe par un brouillon.**
Une page de livre ne devient jamais une fiche directement — elle devient un `import_draft`
que l'on révise, puis que l'on *commit*. C'est ce qui protège le vault d'une lecture
approximative.

⚠️ `commit` rend `visible: false` de façon **structurelle** et non exceptionnelle : la
fiche transite par Dropbox, que le mount VPS ne reflète qu'après ~30 s. Le dire est un
choix juste — sinon un import réussi passe pour un échec.

## A. Acquérir depuis le web (11 cas)

Rôles : **R7** (le compositeur) et **R1** (le planificateur qui manque de variété).
Mesures : `CORPUS_WEB_JSONLD.md` et recipe-manager#4.

⚠️ **La brique existe déjà — c'est son exposition et sa qualité qui manquent.**
`POST /parse-url` (recipe-manager) porte une cascade complète. CM2 ne l'expose pas, et la
cascade ne descend jamais (recipe-manager#4).

| # | Situation | Cvt | Rôle | Système actuel |
|---|---|---|---|---|
| SC-33 | Coller une URL de recette → brouillon proposé | **P** | R7 | `/parse-url` existe chez recipe-manager ; **aucun endpoint CM2 ne l'expose**, et il ne crée pas de `import_draft` |
| SC-34 | L'URL rend un JSON-LD complet (750g, Ricardo) | **M** | R7 | mesuré : 25/34 des URLs ont des étapes |
| SC-35 | L'URL rend un JSON-LD **dégradé** (0 quantité, 0 étape) → descendre d'un tier | **A** | R7 | mesuré : la cascade s'arrête, `recipe.ingredients` suffit à accepter → recipe-manager#4 |
| SC-36 | L'URL est une page de **catégorie** déguisée en recette | **A** | R7 | mesuré sur les deux implémentations : 14 ingrédients agrégés acceptés |
| SC-37 | Le site n'expose son JSON-LD qu'après rendu JS | **M** | R7 | `fetch_html` (recipe-manager) le récupère en direct ; deep-research passe par HydraSpecter |
| SC-38 | `robots.txt` interdit l'URL → refus explicite, pas un échec muet | P | R7 | `_robots_allowed()` chez deep-research ; non vérifié côté recipe-manager |
| SC-39 | Chercher une recette par envie (« un bowl au poisson »), sans URL | **A** | R7 | lane `recipe_web` existe chez deep-research, non branchée |
| SC-40 | La recette trouvée est **carnée** → proposer la réparation avant import | A | R1 | le moteur sait le faire (§F), il n'est pas dans le flux d'import |
| SC-41 | La recette porte un aliment qu'un convive refuse → le dire à l'import | A | R1 | `check_ingredients()` existe, pas appelé à l'import |
| SC-42 | Import en lot (30 recettes pour étoffer le répertoire) | A | R1 | fait **une fois à la main** le 2026-09-02, aucun outil |
| SC-43 | Ré-extraire une recette importée quand le parseur s'améliore | A | R7 | impossible : le document source n'est pas conservé → recipe-manager#3 |

⚠️ **Le piège, mesuré** : la présence d'ingrédients ne signifie pas « recette utilisable ».
Un import branché dessus créerait des fiches sans quantités ni étapes — donc ni courses,
ni macros, ni substitution. Le critère est **étapes non vides ET quantités présentes**.

## B. Acquérir depuis un livre photographié (6 cas)

Rôle : **R7**. Analyse complète : `ANALYSE_import-livre-cuisine.md`.

| # | Situation | Cvt | Rôle | Système actuel |
|---|---|---|---|---|
| SC-44 | Photographier une double page → brouillon structuré | **M** | R7 | `POST /api/recipes/import` → recipe-manager (vision LLM) |
| SC-45 | Plusieurs pages en une fois | M | R7 | `files: list[UploadFile]` |
| SC-46 | Sous-sections du livre (« Pour la farce ») préservées | M | R7 | mappées sur des `###` — c'est ce qui avait vidé 5 recettes (#58) |
| SC-47 | Rendement non numérique (« POUR UNE TRENTAINE DE BISCUITS ») | P | R7 | reconnu comme piège ; conséquence sur les macros non tranchée |
| SC-48 | Le texte du livre est sous droit d'auteur → jamais republié par l'API | P | R7 | cadre posé dans l'analyse, **aucune garde technique** |
| SC-49 | Photo du livre → image de la fiche | **A** | R7 | interdit par SC-48 ; passer par `POST /recipes/{slug}/generate-image` |

## C. Acquérir depuis ce qu'on a réellement acheté (4 cas)

Rôle : **R2** (l'acheteur). Incident fondateur : 2026-08-04, **1 repas relié sur 20**.

| # | Situation | Cvt | Rôle | Système actuel |
|---|---|---|---|---|
| SC-50 | Un repas au menu n'a pas de fiche → les courses l'ignorent | **P** | R2 | `meals_unmatched` le signale ; rien ne le répare |
| SC-51 | Générer la fiche manquante depuis le panier (ingrédients **ancrés sur l'acheté**) | A | R2 | fait à la main le 2026-08-04, jamais outillé |
| SC-52 | Repas de restes → **pas** de fiche, par conception | **M** | R2 | `<slot>_leftovers: true` → `meals_leftovers` |
| SC-53 | Relier explicitement un repas à sa fiche | **M** | R1 | `<slot>_slug:` court-circuite l'heuristique de titre |

## D. Réviser un brouillon avant de l'accepter (5 cas)

Rôle : **R7**. Le garde-fou commun à toutes les voies d'acquisition. Table `import_draft`.

| # | Situation | Cvt | Rôle | Système actuel |
|---|---|---|---|---|
| SC-54 | Lister les brouillons en attente | **M** | R7 | `GET /api/recipes/import/drafts?status=pending` |
| SC-55 | Corriger un champ mal lu avant commit | M | R7 | `PATCH …/drafts/{id}` |
| SC-56 | Jeter un brouillon | M | R7 | `DELETE …/drafts/{id}` |
| SC-57 | Commit → fiche au vault, **`visible: false` assumé** (~30 s) | M | R7 | `POST …/drafts/{id}/commit` |
| SC-58 | Le slug existe déjà → écraser ou refuser | P | R7 | `overwrite: bool` ; ne distingue pas un doublon d'une **fiche jumelle** légitime (SC-67) |

## E. Faire ressortir le répertoire (4 cas) — issue #72

Rôle : **R1**. Le constat fondateur — et ce n'est **pas** un problème d'acquisition.

| # | Situation | Cvt | Rôle | Système actuel |
|---|---|---|---|---|
| SC-59 | Composer un menu en **partant** des recettes existantes | **A** | R1 | le Coach Nutrition ne voit que le garde-manger, jamais le répertoire |
| SC-60 | « Qu'est-ce que je sais faire qui colle à ces macros ? » | A | R1 | `macros_*` et `protein_density` sont en base, aucune requête ne les croise |
| SC-61 | Ne pas re-proposer ce qu'on vient de manger | P | R1 | `recipe_execution` et `execution_count` existent, non consommés |
| SC-62 | Voir qu'un plat « inventé » existe déjà en fiche | A | R1 | c'est exactement ce qui a échoué le 2026-09-01 |

## F. Réparer une recette incompatible (6 cas)

Rôle : **R1**. Mesures : `CORPUS_ACCOMMODATIONS.md`.

| # | Situation | Cvt | Rôle | Système actuel |
|---|---|---|---|---|
| SC-63 | Recette carnée → substitut adapté à la cuisine du plat | **M** | R1 | `repairs` dans `/compatibility`, borné par `rule_applies()` |
| SC-64 | Mijoté décrit sans le mot « mijoter » → détecté quand même | M | R1 | `has_anchored_stew()` — liquide **ET** durée **ET** protéine nommée |
| SC-65 | L'étape qui sert un convive ne pilote pas le contexte du plat | M | R1 | `is_accommodation_step()` |
| SC-66 | Proposer **le libre-service**, technique la plus pratiquée du foyer | **A** | R1 | `self_service` est au vocabulaire (4 observations) ; `repairs` ne le propose pas |
| SC-67 | Proposer la **fiche jumelle** existante plutôt qu'une substitution recomposée | **A** | R1 | 2 des 3 substitutions du vault sont des fiches jumelles |
| SC-68 | Une étape préparatoire ne définit pas le mode de cuisson du plat | **A** | R1 | « faites revenir » → `pan-fried` fait gagner *dorade* (150) sur *lotte* (135) |

## Ce que ce catalogue rend visible

**1. Toutes les voies d'acquisition devraient converger sur `import_draft`.** Le livre y
passe déjà (§B → §D). Le web ne l'a pas (§A), le panier non plus (§C). Y brancher
l'acquisition web réutilise la révision, le commit et la garde `overwrite` au lieu d'en
réinventer trois.

**2. Le moteur de réparation n'est pas dans le flux d'acquisition.** SC-40, SC-41 et SC-63
font le même travail à deux moments différents. Réparer *à l'import* évite de faire entrer
une fiche que personne ne peut manger.

**3. §E ne se résout par aucune acquisition.** Importer 30 recettes de plus ne fera pas que
le menu les utilise. C'est un problème de **restitution**, et c'est le plus coûteux constaté.

## Questions ouvertes

- **Un neuvième rôle ?** L'acquisition n'est ni R1 (planifier la semaine) ni R7 (composer
  un repas) : alimenter le répertoire est un moment à soi, sans repas en vue. `MOMENTS.md`
  dit qu'un moment sans scénario saute — celui-ci en a onze. La décision appartient à
  `MOMENTS.md`, pas ici. *(R8 est déjà pris par le régisseur de la tablée.)*
- **SC-58 vs SC-67** : la fiche jumelle est-elle un doublon à refuser, ou la forme normale
  d'une substitution ? Le corpus dit la seconde ; `overwrite` ne sait pas les distinguer.
- **Le doublon d'extraction** entre recipe-manager et deep-research (deep-research#51).
