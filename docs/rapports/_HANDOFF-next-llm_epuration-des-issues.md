---
title: Handoff — épurer les 103 issues ouvertes, par brainstorming
date: 2026-09-26
commit: 089a7f8
branch: master
project: 2026.08 Cooking Manager 2
github: theflysurfer/cooking-manager-2
---

# Handoff : l'épuration des issues

## L'objet de la prochaine session

**Brainstormer en profondeur les issues ouvertes, puis épurer.** Julien : *« certaines ne
sont peut-être pas d'actualité »*. Ce n'est pas un tri mécanique par label — c'est un
jugement sujet par sujet, et il demande de lire le code avant de conclure.

⛔ **Ne pas fermer une issue sans avoir regardé le code.** Quatre issues ont été fermées le
25/09 alors que leur code était livré depuis des jours (#86, #113, #155, #157) : le plan
mentait sur sa charge. Le symétrique est aussi vrai — une issue peut décrire un sujet réel
dont le code a changé de forme sans le résoudre.

## Le compte, et le piège qui l'avait faussé

**103 issues ouvertes** (mesuré le 2026-09-25), dont 10 en `state:idea`.
Répartition par mois de création : **40 en 2026-08**, **63 en 2026-09**.

⚠️ **`gh issue list` plafonne à 30 sans `--limit`, et rend exactement ce qu'on lui demande
avec.** Un `--limit 60` a rendu 60 lignes qui ont été lues comme un total : 43 issues
n'étaient jamais apparues, et #82 a été déclarée fermée alors qu'elle est ouverte.
La commande qui mesure :

```bash
gh issue list --state open --limit 200 --json number,title,labels
```

Famille « signal absent » du CLAUDE.md global : un plafond se lit comme un total.

## Ce qui est vivant, et ne se remet pas en cause

Les **sept états du menu au panier** (#154) sont tous portés par du code depuis le 25/09.
Le gate de commande est éprouvé contre le vrai drive **par ses deux refus** (panier vide,
panier divergent). Ne pas rouvrir ce chantier ; sa seule réserve est ci-dessous.

Le **PLAN phase 3** (`docs/conception/PLAN_referentiel-aliment-produit-phase3.md`) a ses
étapes 1 à 4 exécutées ; seule l'**étape 5** manque (`GET /api/pantry/cookable`, #133) —
vérifié absent de `backend/app.py`.

## Trois vérifications à faire d'abord — elles changent le compte

| Issue | Ce qu'il faut regarder | Hypothèse à confirmer, jamais à supposer |
|---|---|---|
| **#65** macros déclarées à la main | `/api/recipes/{slug}/macros`, `coverage` | 17 recettes sur 21 concluantes (21/09) — l'issue décrit-elle encore un manque ? |
| **#13** retrait d'un article du panier Auchan | façade REST `:3853/cart/items/remove` (posée le 25/09) | le geste existe ; l'issue parle du MCP, pas de la façade |
| **#82** mémoire du choix produit | `shopping_product`, `COUNT(DISTINCT session_id)` | décidé le 25/09 « dérivé, pas stocké » — livré ou pas ? |

## Les quatre familles du fond de backlog, jamais commencées

Ce sont elles qui portent la question « est-ce encore d'actualité ». Aucune n'est sur le
chemin critique des courses.

| Famille | Issues | La question à poser |
|---|---|---|
| Intents vocaux garde-manger + TTS | #38–#45, #48, #50 | le micro est masqué sur l'iPad mini (Safari 12.5.8, #152) — à quoi sert un intent sans micro ? |
| Écrans manquants | #68, #30, #49, #56, #57 | lesquels servent un geste réel du dimanche, lesquels sont des envies de 2026-08 ? |
| Prix, budget, comparaison drives | #18, #19, #55, #21 | #149 (le référentiel apprend le prix) les recouvre-t-il ? |
| Autres drives, exploration | #17, #20, #26, #52 | à archiver en `state:idea` plutôt qu'à garder ouvertes ? |

Les 10 `state:idea` (#134–#143) sont un carnet de recettes et d'inspirations : **ne pas les
traiter comme des chantiers**, ils n'en sont pas.

## Ce que ce cadre attend encore, côté chaîne des courses

- État 2 : **#94** (rien ne décrémente le garde-manger — panne d'origine du 09/09, jamais
  refermée), #118, #120, #69
- État 4 : **#82**, #149
- Parts de convive : #108 · Récurrents figés : #107 · Arbitrage : #147
- **#144 + #145** : 150 arbitrages bloqués — 114 attendent une fiche `food` inexistante,
  36 une valeur de `food_kinds` absente. Tant qu'ils attendent, macros et couverture
  méditerranéenne mesurent sur un trou.

## La seule dette qu'aucune issue ne porte

**Le chemin nominal du gate n'a jamais été mené jusqu'au bout** : aucun panier conforme n'est
allé jusqu'à l'URL de paiement. Les deux refus sont mesurés, le succès ne l'est pas. À faire
avec un vrai panier de la semaine, pas avec un panier de test.

## Méthode suggérée pour la session

1. Mesurer le compte réel avec `--limit 200` (jamais sans).
2. Trancher les trois vérifications ci-dessus — elles se font en lisant du code, pas en
   discutant.
3. Brainstormer famille par famille, pas issue par issue : les quatre familles ci-dessus
   portent chacune une question unique qui décide de 4 à 10 issues d'un coup.
4. Pour chaque issue écartée : la fermer **avec son motif**, ou la basculer en
   `state:idea`. Une issue fermée sans motif reviendra.

## Contexte technique

- Tout est déployé sur srv759970 : `cooking-manager` (8795), `mcp-vps-auchan` (3854),
  `mcp-vps-auchan-rest` (3853). Vérifié `active` le 25/09 à 23 h 50.
- `mcp-vps-auchan` : 32 tests passés, zéro échec (mcp-vps#188 fermée).
- Dernier diary : `docs/rapports/2026.09.25_23.50_5b95538_SESSION_handoff-solde-deploiement-et-sept-etats.md`
- Le cadre du graphe : issue **#154**, commentée le 25/09 avec son état mesuré et sa rectification.
