---
title: Nomenclature des tests — Cooking Manager
axis: quality
upstream: [MOMENTS.md, USE_CASES_TABLEE.md, USE_CASES_COURSES.md, USE_CASES_RECETTES.md, "product-conception-toolkit/docs/MODEL_test_nomenclature.md"]
status: draft
date: 2026-09-03
---

# Nomenclature des tests

> Doctrine générale : `product-conception-toolkit/docs/MODEL_test_nomenclature.md`
> (scindé de `2026.08 Product Toolkit` le 2026-09-03, voir son ADR 0001).
> Ce document est l'**instance locale** — il catalogue les SC-NN de ce projet et
> trace la migration des tests existants.
>
> ⚠️ **Ce projet produit des `SC-NN` depuis quatre documents**, pas seulement
> `MOMENTS.md` : `USE_CASES_TABLEE.md` (SC-25 à SC-32), `USE_CASES_COURSES.md`
> (numérotation propre par section, non `SC-NN`) et `USE_CASES_RECETTES.md`
> (SC-33 à SC-68). Ce catalogue était resté à SC-24 pendant que `USE_CASES_TABLEE.md`
> occupait déjà SC-25 à SC-32 sans y être enregistré — la collision qui a motivé
> la scission ci-dessus. Vérifier ce tableau avant de réserver un nouveau bloc de SC-NN.

## Catalogue des scénarios (SC-NN)

| SC | Rôle | Famille | Description | Étage |
|---|---|---|---|---|
| SC-01 | R1 | conflit-detecté | plat interdit détecté pour un convive présent | unit |
| SC-02 | R1 | conflit-detecté | pas de faux positif (aliment autorisé) | unit |
| SC-03 | R1 | convive-absent | convive absent ce jour → son conflit ne compte pas | unit |
| SC-04 | R1 | menu-sans-option | aucune alternative sans conflit → alerte bloquante | unit |
| SC-05 | R1 | ajout-convive-ponctuel | ajouter un 5e convive pour un repas précis | e2e |
| SC-06 | R2 | agrégation-portions | quantités agrégées convives × portions | unit |
| SC-07 | R2 | différentiel-garde-manger | déduire le stock existant de la liste | unit |
| SC-08 | R2 | achat-manqué | signaler un manque → impact sur repas à venir | e2e |
| SC-09 | R2 | ingrédients-restants-semaine | vue agrégée aujourd'hui → fin de semaine | e2e |
| SC-10 | R3 | étape-suivante-sans-toucher | navigation mains libres entre étapes | e2e |
| SC-11 | R3 | lecture-à-distance | taille de police lisible à 60 cm | compat |
| SC-12 | R4 | appréciation-attribuée | feedback attribué à un convive précis | e2e |
| SC-13 | R4 | pas-de-moyenne-de-groupe | pas d'agrégation foyer sur les appréciations | unit |
| SC-14 | R5 | màj-garde-manger | déclarer un produit restant/épuisé | e2e |
| SC-15 | R5 | rupture-stock | rupture → recalcul des impacts sur les repas | e2e |
| SC-16 | R5 | garde-manger-réactif | alerte visible sur la vue menu (pas de push) | e2e |
| SC-17 | R6 | prep-oubliée | overnight oats non préparés → alerte veille | e2e |
| SC-18 | R6 | décongélation-j-1 | crevettes à décongeler signalées la veille | unit |
| SC-19 | R6 | marinade-anticipée | marinade à lancer la veille | unit |
| SC-20 | R7 | recette-hors-menu | recherche recette hors cycle planifié | e2e |
| SC-21 | R7 | delta-courses | ingrédients manquants = total − stock | unit |
| SC-22 | R7 | repas-improvisé | ajout d'un repas hors menu avec impact courses | e2e |
| SC-23 | J4 | import-url | URL → parseur → fiche recette créée | e2e |
| SC-24 | J4 | import-saisie-libre | texte dicté → fiche recette créée | e2e |
| SC-25 | R8 | trame-tablee | composition habituelle de table (garde × vacances × cantine) | unit |
| SC-26 | R8 | absence-ponctuelle | quelqu'un part — absence hors trame | unit |
| SC-27 | R8 | invite-ponctuel | quelqu'un arrive — invité non déclaré | e2e |
| SC-28 | R8×R1 | repas-externe | repas dehors, pas de cuisine à la maison | e2e |
| SC-29 | R8×R2 | cuisine-emportee | on cuisine mais on mange ailleurs | e2e |
| SC-30 | R8×R1 | sejour-cuisine | séjour où l'on cuisine (Bègles, corrigé 2026-08-12) | e2e |
| SC-31 | R8 | sejour-sans-cuisine | séjour sans cuisine (hôtel, club) | unit |
| SC-32 | R8 | repas-hybride | cas limites de tablée (deux tablées, restes, meal prep) | e2e |
| SC-33 | R7 | url-cascade | coller une URL → brouillon proposé, cascade descend si dégradé | e2e |
| SC-34 | R7 | url-jsonld-complet | JSON-LD complet accepté tel quel | unit |
| SC-35 | R7 | url-jsonld-degrade | JSON-LD sans étapes ni quantités → descendre d'un tier | unit |
| SC-36 | R7 | url-page-categorie | une page de liste ne doit pas être acceptée comme recette | unit |
| SC-37 | R7 | url-rendu-js | site n'exposant son JSON-LD qu'après rendu JS | e2e |
| SC-38 | R7 | url-robots | `robots.txt` interdit → refus explicite | unit |
| SC-39 | R7 | recette-par-envie | chercher une recette par envie, sans URL | e2e |
| SC-40 | R1 | reparation-avant-import | recette carnée → réparation proposée avant import | e2e |
| SC-41 | R1 | conflit-avant-import | aliment refusé par un convive → dit à l'import | e2e |
| SC-42 | R1 | import-en-lot | importer plusieurs recettes en une fois | e2e |
| SC-43 | R7 | re-extraction | ré-extraire une recette quand le parseur s'améliore | unit |
| SC-44 | R7 | livre-photo | photographier une double page → brouillon structuré | e2e |
| SC-45 | R7 | livre-multi-pages | plusieurs pages en une fois | e2e |
| SC-46 | R7 | livre-sous-sections | sous-sections du livre préservées (« Pour la farce ») | unit |
| SC-47 | R7 | livre-rendement-non-numerique | rendement non numérique (« pour une trentaine ») | unit |
| SC-48 | R7 | livre-droit-auteur | texte sous droit d'auteur jamais republié par l'API | unit |
| SC-49 | R7 | livre-image-interdite | photo du livre → jamais utilisée comme image de fiche | unit |
| SC-50 | R2 | repas-sans-fiche | repas au menu sans fiche → courses l'ignorent | unit |
| SC-51 | R2 | fiche-depuis-panier | générer une fiche depuis le panier acheté | e2e |
| SC-52 | R2 | repas-restes | repas de restes → pas de fiche, par conception | unit |
| SC-53 | R1 | repas-slug-explicite | relier explicitement un repas à sa fiche | unit |
| SC-54 | R7 | drafts-lister | lister les brouillons en attente | unit |
| SC-55 | R7 | drafts-corriger | corriger un champ avant commit | unit |
| SC-56 | R7 | drafts-jeter | jeter un brouillon | unit |
| SC-57 | R7 | drafts-commit | commit → fiche au vault, visible=false assumé | e2e |
| SC-58 | R7 | drafts-slug-existant | slug déjà pris → écraser ou refuser | unit |
| SC-59 | R1 | menu-depuis-repertoire | composer un menu en partant des recettes existantes | e2e |
| SC-60 | R1 | recette-par-macros | trouver une recette qui colle à des macros cibles | unit |
| SC-61 | R1 | pas-de-repetition | ne pas re-proposer un plat récemment mangé | unit |
| SC-62 | R1 | fiche-deja-existante | voir qu'un plat « inventé » existe déjà en fiche | e2e |
| SC-63 | R1 | reparation-cuisine-adaptee | substitut adapté à la cuisine du plat | unit |
| SC-64 | R1 | mijote-sans-le-mot | mijoté détecté sans le mot « mijoter » | unit |
| SC-65 | R1 | accommodation-hors-contexte | l'étape qui sert un convive ne pilote pas le plat | unit |
| SC-66 | R1 | reparation-libre-service | proposer le libre-service comme réparation | unit |
| SC-67 | R1 | reparation-fiche-jumelle | proposer la fiche jumelle plutôt qu'une substitution | unit |
| SC-68 | R1 | etape-preparatoire-neutre | une étape préparatoire ne définit pas le mode de cuisson | unit |

## Migration des tests existants

| Fichier actuel | Scénarios couverts | Action |
|---|---|---|
| `test_convives.py` | SC-01, SC-02, SC-03 (partiellement) | annoter les fonctions |
| `test_e2e_menus.py` | non-rég #4 (pas un SC) | garder tel quel |
| `test_e2e_nonreg.py` | smoke routes (transverse) | garder tel quel |
| `test_normalizer.py` | logique slug (transverse) | garder tel quel |
| `test_ingredients.py` | parsing ingrédients (transverse) | garder tel quel |
| `test_presence.py` | SC-03 (partiellement) | annoter |
| `test_pantry.py` | SC-14 (partiellement) | annoter |

## Vérification

```bash
grep -oP 'SC-\d+' docs/conception/MOMENTS.md | sort -u > /tmp/sc_moments
grep -roPh 'SC-\d+' tests/ | sort -u > /tmp/sc_tests
comm -23 /tmp/sc_moments /tmp/sc_tests
```
