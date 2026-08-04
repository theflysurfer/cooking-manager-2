---
title: Les parties prenantes de Cooking Manager
axis: stakeholder
skill: julien-stakeholders
proof_level: mixte
upstream: []
downstream: [../conception/MOMENTS.md]
status: draft
date: 2026-08-04
---

# Qui subit le menu — même sans ouvrir l'application

Ce document dit **QUI**. Ce que chacun *fait* (planifier, acheter, cuisiner) est l'axe usage,
dans `MOMENTS.md`. La règle fondatrice de ce projet : **un stakeholder peut être affecté sans
jamais être utilisateur.** Raisonner en « utilisateurs » a produit, le 2026-08-04, un repas
planifié sans rien pour Clémence.

⚠️ Chaque fiche porte son niveau : `qualitatif` (attesté par la base `convive`) ou `provisoire`
(qui porte réellement quel rôle chez nous n'est pas dérivable — à confronter).

## A. Le foyer — quatre personnes, dont certaines n'ouvrent jamais l'app

### A1. Clémence — *qualitatif* ⚠️ le cas fondateur
- **Contrainte** : ne mange pas de poulet ; refuse l'œuf dur.
- **Elle n'ouvre pas l'application**, et pourtant un menu qui l'ignore est un menu **faux**.
- **Preuve** : table `convive` ; conflit détecté le 2026-08-04 (poulet du mardi + œuf de la salade
  niçoise du lundi). Sans la contrainte modélisée, elle était invisible.

### A2. Léa — *qualitatif*
- **Contrainte** : refuse l'œuf dur (comme Clémence).
- **Preuve** : le conflit œuf de lundi la concernait **aussi** — *personne ne l'avait vu*. C'est
  l'argument même contre le raisonnement « utilisateur » : deux personnes affectées, un seul repas.

### A3. Les autres convives — *qualitatif (existence) / provisoire (préférences)*
- 14 convives ingérés dans la base ; leurs contraintes sont attestées, leurs **goûts** restent à
  mesurer (ne pas moyenner un « 5/5 en famille » — voir l'attribution ci-dessous).

## B. L'opérateur — Julien

Julien **décide et opère** le menu. Il cumule aussi cinq casquettes d'usage (planificateur,
acheteur, cuisinier, convive, intendant) — mais celles-ci sont des `role` d'usage : elles vivent
dans `MOMENTS.md`, pas ici. Ici, il est **le décideur du menu** et **le seul utilisateur de l'app**.

## Le piège d'attribution — ne jamais moyenner un signal de foyer

`recipe_execution.appreciated_by` est un `TEXT[]` : un plat noté 5/5 « en famille » ne dit pas
**qui** a aimé. Un signal non attribuable à une personne est **écarté, pas moyenné** (invariant
partagé avec le profil de goût d'Avignon). Sans quoi le goût d'un tiers est pris pour celui d'un
autre — la contamination du foyer, en cuisine.

## Ce que ce document révèle

1. **Le centre de décision du menu est collectif** (Julien décide, Clémence co-contraint) mais
   **une seule personne ouvre l'app**. Modéliser les utilisateurs seuls efface les co-décideurs.
2. **Qui porte quel rôle** au quotidien est `provisoire` : c'est la seule donnée que ni le code
   ni l'analyse ne peuvent inventer sans optimiser pour des utilisateurs imaginaires.
