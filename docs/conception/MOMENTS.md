---
title: Moments d'usage — Cooking Manager
axis: usage
proof_level: provisional
upstream: [../marque/STAKEHOLDERS.md]
downstream: [julien-test-case-design]
status: draft
date: 2026-08-04
---

# Moments d'usage

> Un moment ne décore pas : il produit les scénarios de test. Chaque moment porte la famille de
> scénarios qu'il engendre. Un moment sans scénario saute.

Le foyer compte quatre personnes, mais **Julien porte cinq casquettes dans la même journée**. Un
persona « Julien, 43 ans » ne discrimine aucune décision d'écran ; le `role` à cet instant, si.
Chaque moment = `role` × situation × **contrainte matérielle**.

## Les cinq rôles (casquettes), et leur moment

### R1. Le planificateur — le dimanche, au calme
> *Quand je prépare la semaine le dimanche, je veux composer un menu qui respecte les contraintes
> de chaque convive, afin de ne pas découvrir un conflit au moment de cuisiner.*
- **Situation/contrainte** : assis, au calme, vue d'ensemble ; a besoin de voir les conflits **avant**.
- **Famille de scénarios** : `conflit-detecté`, `convive-absent`, `menu-sans-option-pour-X`.

### R2. L'acheteur — le lundi, sur le drive
> *Quand je commande les courses, je veux la liste agrégée par les quantités réelles (convives ×
> portions), afin de ne pas racheter ce que le placard contient déjà.*
- **Contrainte** : passe par le drive Auchan ; le garde-manger doit être à jour.
- **Famille** : `agrégation-portions`, `différentiel-garde-manger`, `acheter-du-miel-qu-on-avait-déjà`.

### R3. Le cuisinier — le soir, mains grasses, iPad à 60 cm
> *Quand je cuisine le soir, je veux suivre la recette sans toucher l'écran, afin de ne pas
> l'salir ni perdre ma place.*
- **Contrainte matérielle** : mains sales, iPad posé à distance, lecture à 60 cm. **Même tâche,
  contrainte différente = moment différent** de R1.
- **Famille** : `étape-suivante-sans-toucher`, `lecture-à-distance`, `minuteur-parallèle`.
- ⚠️ **Le canal du geste reste à trancher** (tape ? dicte ? trois boutons ?) — non dérivable.

### R4. Le convive — à table
> *Quand un plat me plaît, je veux que ça compte pour moi précisément, afin que les prochaines
> semaines s'améliorent.*
- **Contrainte** : le retour doit s'**attribuer à la personne**, jamais au foyer (cf. STAKEHOLDERS).
- **Famille** : `appréciation-attribuée`, `pas-de-moyenne-de-groupe`.

### R5. L'intendant — devant le placard
> *Quand je range les courses, je veux mettre à jour ce qui reste, afin que la planification et
> l'achat suivants partent du vrai stock.*
- **Famille** : `màj-garde-manger`, `péremption`, `stock-négatif-impossible`.

## Anti-usage (à qui / à quand on ne s'adresse pas)

- **Le cuisinier d'inspiration** qui n'aime pas planifier : un réseau de recettes le sert mieux.
- **Le foyer sans contrainte alimentaire** : le cœur du produit (la détection de conflits) ne lui
  sert à rien — l'optimiser pour lui dilue le seul terrain où l'on gagne.

## Reste à trancher (avec Julien et Clémence, pas dérivable)

- **Le canal du geste** de R3 (mains grasses, iPad à distance).
- **Qui porte réellement quel rôle** — R1 à R5 sont attribués à Julien par défaut ; à confirmer.
