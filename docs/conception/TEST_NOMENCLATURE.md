---
title: Nomenclature des tests — Cooking Manager
axis: quality
upstream: [MOMENTS.md, julien-test-case-design]
status: draft
date: 2026-08-06
---

# Nomenclature des tests

> Un moment sans scénario saute. Un scénario sans test n'existe pas.

## Principes

1. **Le scénario est l'atome du test** (VOCABULARY.md, Product Toolkit). Le moment est
   l'atome du design — il *engendre* les scénarios, il ne les remplace pas.
2. **Chaque scénario porte un identifiant `SC-NN`** stable, attribué une fois dans
   MOMENTS.md et jamais réutilisé. Le numéro est global au projet (pas par rôle).
3. **Le test référence le scénario, pas le module.** Un fichier de test peut couvrir
   plusieurs scénarios du même rôle ; une fonction de test couvre un seul SC-NN.

## Convention de nommage

### Fichiers de test

```
tests/test_<étage>_<rôle>_<domaine>.py
```

| Segment | Valeurs | Exemples |
|---|---|---|
| `<étage>` | `unit`, `e2e`, `compat` | étage 1 = logique pure, étage 2 = parcours réel, étage 3 = compat device |
| `<rôle>` | `r1`…`r7`, ou omis si transverse | `r1` = planificateur, `r3` = cuisinier |
| `<domaine>` | slug libre, court | `compatibility`, `stock`, `prep`, `swap` |

Exemples :
- `test_unit_r1_compatibility.py` — logique de détection de conflits (R1 planificateur)
- `test_e2e_r2_shopping.py` — parcours achat drive (R2 acheteur)
- `test_e2e_r5_stock.py` — mise à jour garde-manger (R5 intendant)
- `test_unit_r6_prep.py` — checklist préparation veille (R6 préparateur)
- `test_e2e_import.py` — import de recette (J4, transverse, pas de rôle unique)

### Fonctions de test

```python
def test_sc<NN>_<slug_court>(…):
    """SC-<NN> — <description en une ligne>."""
```

Le préfixe `sc<NN>` fait le lien mécanique avec MOMENTS.md. Le slug court décrit
le cas. Exemple :

```python
def test_sc01_conflict_detected_pescetarian(menu_with_chicken, clemence):
    """SC-01 — un plat à base de poulet est signalé pour un convive pescétarien."""
    alerts = check_meal(menu_with_chicken, [clemence])
    assert any(a.severity == "error" for a in alerts)

def test_sc02_no_false_positive_fish(menu_with_salmon, clemence):
    """SC-02 — un plat à base de saumon ne déclenche pas d'alerte pour un pescétarien."""
    alerts = check_meal(menu_with_salmon, [clemence])
    assert not alerts
```

### Non-régressions

Un test de non-régression (bug corrigé) porte le numéro d'issue GitHub :

```python
def test_nonreg_issue04_ingest_does_not_delete_menus(…):
    """Non-rég #4 — l'ingestion de recettes ne doit plus effacer les menus."""
```

Pas de SC-NN : une non-régression n'est pas un scénario d'usage, c'est un verrou
sur un bug passé.

## Catalogue des scénarios (SC-NN)

Chaque scénario est attribué à un moment (R + famille) et à un étage de test.

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

Les tests actuels n'ont pas de SC-NN. La migration est **incrémentale** : on ne
renomme pas les tests existants d'un coup, on attribue un SC-NN à chaque nouveau
test et on annote les existants quand on les touche.

| Fichier actuel | Scénarios couverts | Action |
|---|---|---|
| `test_convives.py` | SC-01, SC-02, SC-03 (partiellement) | annoter les fonctions |
| `test_e2e_menus.py` | non-rég #4 (pas un SC) | garder tel quel |
| `test_e2e_nonreg.py` | smoke routes (transverse) | garder tel quel |
| `test_normalizer.py` | logique slug (transverse) | garder tel quel |
| `test_ingredients.py` | parsing ingrédients (transverse) | garder tel quel |
| `test_presence.py` | SC-03 (partiellement) | annoter |
| `test_pantry.py` | SC-14 (partiellement) | annoter |

## Lien avec julien-test-case-design

La skill `julien-test-case-design` produit une suite en trois étages :

| Étage skill | Correspond à | Marqueur pytest |
|---|---|---|
| Étage 1 — logique pure | `test_unit_*` | (pas de marqueur, défaut) |
| Étage 2 — parcours réels | `test_e2e_*` | `@pytest.mark.e2e` |
| Étage 3 — mise en page/gestes | `test_compat_*` | `@pytest.mark.compat` |

Quand la skill est invoquée sur ce projet, elle lit ce document + MOMENTS.md pour
dériver les scénarios manquants et les tests à écrire.
