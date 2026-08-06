---
title: Nomenclature des tests — Cooking Manager
axis: quality
upstream: [MOMENTS.md, "2026.08 Product Toolkit/docs/MODEL_test_nomenclature.md"]
status: draft
date: 2026-08-06
---

# Nomenclature des tests

> Doctrine générale : `2026.08 Product Toolkit/docs/MODEL_test_nomenclature.md`.
> Ce document est l'**instance locale** — il catalogue les SC-NN de ce projet et
> trace la migration des tests existants.

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
