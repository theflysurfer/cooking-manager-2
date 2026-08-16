---
title: Cas d'usage — Courses multi-canal
axis: usage
proof_level: provisional
upstream: [MOMENTS.md, USE_CASES_TABLEE.md, ../marque/STAKEHOLDERS.md]
downstream: [julien-test-case-design, cooking-manager-weekly-pipeline]
status: draft
date: 2026-08-16
---

# Cas d'usage — Courses

> **Un tour de courses** = une sortie, un canal, un moment. Le drive de lundi,
> le marché de samedi, le boucher en passant jeudi. Ce n'est pas « la liste de
> courses » : la liste n'existe pas comme objet, elle est le résidu d'un calcul.
>
> Constat fondateur, 2026-08-16 : la liste paraît **persistante** alors qu'elle
> n'est **pas persistée du tout**. `GET /api/menus/{slug}/shopping-list` la
> recalcule à chaque appel ; le front la garde en RAM (`state.shopping`). Elle
> n'est datée par rien, ses lignes n'ont pas d'état, elle ne se clôt jamais.
> Un objet sans début ni fin se lit comme permanent.

## Ce qui existe aujourd'hui

| Brique | Rôle réel | Fichier |
|---|---|---|
| `/api/menus/{slug}/shopping-list` | calcul du **besoin**, à la volée, jamais stocké | `backend/app.py:536` |
| `shopping_session` | **compte rendu d'après coup** d'une commande drive (date, store, cart_id, total) | `backend/db.py:62` |
| `shopping_product` | produits réellement achetés, avec nutrition scrapée | `backend/db.py:75` |
| `shopping_preference` | préférences produit (`pref_type`, `key`, `value`) — blacklists | `backend/db.py:104` |

`shopping_session.store` existe déjà en TEXT, mais **rien en amont ne dit où une
ligne doit être achetée**. Le seul canal câblé est Auchan Drive (via le MCP VPS).

## Les quatre dimensions indépendantes

| Dim | Question | Impact système |
|---|---|---|
| **Besoin** (B) | Quoi, combien ? | Menu × tablée × garde-manger — déjà calculé |
| **Canal** (C) | Où l'acheter ? | Attribution des lignes, format de sortie |
| **Cadence** (K) | Quand y va-t-on ? | Ce qui doit être acheté *avant* tel repas |
| **Preuve** (P) | Qu'est-ce qui confirme l'achat ? | Alimentation du garde-manger, fiabilité du résidu |

Le système actuel ne modélise que **B**, et suppose C, K, P constants (= Auchan
Drive, une fois par semaine, facture du drive).

## Décisions prises (2026-08-16, avec Julien)

1. **Un plan = un tour.** Pas d'objet hebdomadaire chapeau. Conséquence
   directe : plus rien ne garantit que la semaine est couverte → c'est le
   **besoin résiduel** qui porte cet invariant (§ suivant).
2. **Multi-drive par habitude**, pas par arbitrage de prix. Il faut donc une
   **mémoire** d'attribution, *et* un mécanisme de **réattribution** ponctuelle
   — car l'habitude n'est pas une règle : certaines semaines, on ne veut pas
   aller au marché.
3. **Exécution en magasin sur téléphone** (marché, boucher, bio). Nouvelle cible
   d'affichage : l'app vise l'iPad mini posé en cuisine, pas un écran tenu debout
   d'une main dans une allée.

## L'invariant : le besoin résiduel

```
besoin_résiduel = besoin(menu, tablée)
                − garde-manger
                − lignes engagées dans les tours OUVERTS
```

C'est ce que « plan = un tour » remplace le plan hebdo par. Deux propriétés
non négociables :

- **Un tour ouvert réserve ses lignes.** Sans ça, deux tours successifs
  proposent deux fois la même chose, ou en oublient.
- **Le besoin est recalculable, le tour est figé.** Si une recette change après
  l'ouverture d'un tour, le tour **ne se réécrit pas tout seul** — il signale
  l'écart. Sinon un article déjà coché redevient à acheter, et on rachète.

## Attribution d'une ligne à un canal — trois sources hiérarchisées

Même patron que les macros (`nutrition.py`) : jamais d'estimation implicite.

| Rang | Source | Persistance |
|---|---|---|
| 1 | **Réattribution ponctuelle** — « cette fois, le pain au drive » | le tour seul |
| 2 | **Mémoire d'habitude** — « le pain → boulangerie » | `shopping_preference(pref_type='channel')` |
| 3 | **Défaut par rayon** | code |
| — | **`non attribué`** — état visible, jamais deviné en silence | affiché, bloquant à la clôture |

⚠️ La réattribution **n'écrase pas** la mémoire. Renoncer au marché cette
semaine ne doit pas désapprendre que les œufs viennent du marché. Une mémoire
qui se réécrit à chaque exception s'efface en trois semaines.

## Le canal n'est pas une étiquette

Ce qui change le calcul, pour chaque canal :

| Attribut | Drive Auchan | Marché | Boucher | Bio | Boulangerie |
|---|---|---|---|---|---|
| Catalogue interrogeable | oui (MCP) | non | non | partiel | non |
| Quantités exactes possibles | oui | non (« à l'œil ») | oui (au poids) | oui | non |
| Cadence | créneau réservé | samedi matin | ponctuel | ponctuel | quotidien |
| Preuve d'achat | facture / panier | cochage manuel | cochage manuel | cochage | cochage |
| Délai | J+1 min. | immédiat | immédiat | immédiat | immédiat |

Conséquence : un canal sans catalogue ne peut **pas** produire de
`shopping_product` enrichi (nutrition, EAN, prix/kg). Le garde-manger alimenté
depuis un canal manuel est structurellement moins précis — il faut que ça se
voie, pas que ça se devine.

---

## A. Le tour simple — un canal, l'existant (5 cas)

| # | Situation | Couverture | Dim | Système actuel |
|---|---|---|---|---|
| 1 | Générer le besoin de la semaine depuis le menu | modélisé | B | `/shopping-list` |
| 2 | Déduire le garde-manger du besoin | modélisé | B | différentiel `pantry.py` |
| 3 | Passer la commande drive | modélisé | B C | MCP VPS `mcp-vps-auchan` |
| 4 | Enregistrer ce qui a été acheté | modélisé | P | `shopping_session` + `/persist-cart` |
| 5 | Rouvrir la liste plus tard et retrouver son état | **absent** | K P | rien n'est persisté — recalcul intégral |

## B. Répartition entre canaux (7 cas)

Le cœur du sujet. Aucun de ces cas n'est modélisé : il n'existe pas de champ
« canal » sur une ligne de besoin.

| # | Situation | Couverture | Dim | Système actuel |
|---|---|---|---|---|
| 6 | Voir le besoin de la semaine ventilé par canal | absent | B C | pas de notion de canal |
| 7 | Le pain va à la boulangerie, jamais au drive | absent | C | (préférence alimentaire connue, non modélisée) |
| 8 | La viande va chez le boucher | absent | C | — |
| 9 | Les légumes au marché, le sec au drive | absent | C | — |
| 10 | Une ligne qu'aucune règle ne couvre → `non attribué` | absent | C | — |
| 11 | Un même ingrédient réparti sur deux canaux (moitié/moitié) | absent | B C | — |
| 12 | Deux drives : répartition par habitude entre enseignes | absent | C | un seul drive câblé |

## C. Réattribution et renoncement (6 cas)

L'habitude n'est pas une règle. C'est la catégorie que la décision « par
habitude, mais ça change » rend obligatoire.

| # | Situation | Couverture | Dim | Système actuel |
|---|---|---|---|---|
| 13 | « Pas de marché cette semaine » → basculer ses lignes ailleurs | absent | C K | — |
| 14 | Basculer **une seule** ligne (le reste du canal tient) | absent | C | — |
| 15 | Un canal indisponible (boucher fermé, marché annulé) | absent | C K | — |
| 16 | Renoncer sans réattribuer : la ligne redevient résiduelle | absent | B C | — |
| 17 | La réattribution ne modifie pas la mémoire d'habitude | absent | C | — |
| 18 | Réattribuer vers un canal **déjà clos** cette semaine → refus | absent | C K | — |

## D. Mémoire d'habitude (5 cas)

| # | Situation | Couverture | Dim | Système actuel |
|---|---|---|---|---|
| 19 | Apprendre l'attribution d'un ingrédient après N tours cohérents | absent | C | — |
| 20 | Consulter / corriger les règles apprises (écran dédié) | absent | C | `shopping_preference` existe, sans UI ni `pref_type='channel'` |
| 21 | Une habitude qui change durablement (on quitte le boucher) | absent | C | — |
| 22 | Distinguer « appris » de « déclaré par Julien » | absent | C | pas de provenance sur `shopping_preference` |
| 23 | Une exception répétée 3 fois : proposer de changer la règle | absent | C | — |

## E. Exécution en magasin — téléphone (6 cas)

Nouvelle cible matérielle. **Rien n'existe** : l'app est conçue pour un iPad
mini posé sur un plan de travail.

| # | Situation | Couverture | Dim | Système actuel |
|---|---|---|---|---|
| 24 | Ouvrir la liste d'un canal sur téléphone, debout | absent | C P | pas de vue mobile |
| 25 | Cocher un article d'une main, sans zoom | absent | P | — |
| 26 | Cocher hors réseau (marché couvert, sous-sol) | absent | P | aucune tolérance offline |
| 27 | Saisir un poids réel au lieu du besoin théorique | absent | B P | — |
| 28 | Article introuvable → marquer manquant, pas décocher | absent | P | — |
| 29 | Clore le tour sur place | absent | K P | — |

⚠️ **Contrainte matérielle à trancher** : quel téléphone, quel navigateur ? La
cible iOS 12 de l'iPad mini 2 ne s'applique **pas** mécaniquement ici — mais
ajouter une seconde cible de compatibilité a un coût réel sur `web/`.

## F. Retour d'exécution vers le garde-manger (6 cas)

| # | Situation | Couverture | Dim | Système actuel |
|---|---|---|---|---|
| 30 | Le drive livre → garde-manger mis à jour depuis la facture | partiel | P | `/persist-cart`, déclenché à la main |
| 31 | Un canal manuel → garde-manger depuis les coches | absent | P | — |
| 32 | Substitution (pas de skyr, pris du fromage blanc) | partiel | P | `alternatives` en JSONB, pas de flux |
| 33 | Achat manqué → impact sur les repas à venir | absent | B P | SC-08 de MOMENTS.md, jamais câblé |
| 34 | Un tour manuel n'enrichit pas la nutrition (pas de catalogue) | absent | P | doit être **visible**, pas silencieux |
| 35 | Deux tours alimentent le même garde-manger sans doublon | absent | B P | — |

## G. Temporalité (7 cas)

La catégorie qui répond à « la liste semble persistante ».

| # | Situation | Couverture | Dim | Système actuel |
|---|---|---|---|---|
| 36 | Un tour couvre les repas du X au Y (bornes explicites) | partiel | K | `?from_date=` existe, non persisté |
| 37 | Un tour ouvert réserve ses lignes du besoin résiduel | absent | B K | — |
| 38 | Un tour clos ne réapparaît jamais | absent | K | — |
| 39 | Un tour ouvert dont les repas sont passés se périme visiblement | absent | K | — |
| 40 | Le menu change après ouverture du tour → **signaler l'écart** | absent | B K | recalcul silencieux (l'article coché redeviendrait à acheter) |
| 41 | Historique : « qu'ai-je acheté la semaine du X ? » | partiel | K P | `/api/shopping/sessions` (20 dernières) |
| 42 | Deux tours ouverts simultanément (drive + marché) | absent | B K | — |

## H. Cas limites (5 cas)

| # | Situation | Couverture | Dim | Système actuel |
|---|---|---|---|---|
| 43 | Achat hors besoin (envie, promo) → entre au garde-manger | absent | B P | — |
| 44 | Course d'urgence à 19 h pour le dîner du soir | absent | K | — |
| 45 | Stock long (riz, conserves) acheté en avance, hors menu | absent | B K | — |
| 46 | Courses pour un séjour (F.30 de USE_CASES_TABLEE) — autre lieu | absent | B C | tablée corrigée, courses non |
| 47 | Quelqu'un d'autre fait une partie des courses | absent | C P | pas de notion d'acheteur |

---

## Couverture globale

| État | Nombre | Part |
|---|---|---|
| **Modélisé** | 4 | 8,5 % |
| **Partiel** | 4 | 8,5 % |
| **Absent** | 39 | 83 % |

Détail des partiels : F.30 et F.32 (drive livré / substitution, flux incomplet), G.36 et
G.41 (bornes de date via `?from_date=`, historique des 20 dernières sessions).

Le tour drive mono-canal fonctionne. Le canal, la cadence et la preuve sont
des angles morts complets.

## Priorisation suggérée

1. **G + A.5** — donner un objet daté et clôturable au tour. Sans ça, tout le
   reste s'accroche à du vide, et le symptôme initial (« ça a l'air persistant »)
   reste entier.
2. **B** — le champ canal sur la ligne, et la ventilation. Débloque tout le sujet.
3. **C** — réattribution/renoncement. Inséparable de B : une répartition qu'on ne
   peut pas défaire ne sera pas utilisée.
4. **E** — la vue téléphone. Sans elle, les canaux manuels ne se cochent nulle
   part et la preuve n'entre jamais.
5. **F** — le retour vers le garde-manger depuis les canaux manuels.
6. **D** — la mémoire d'habitude. Confort ; se déclare à la main en attendant.
7. **H** — cas limites.

## Reste à trancher (non dérivable)

- **Cible mobile de E** : quel téléphone / navigateur, et accepte-t-on une
  seconde matrice de compatibilité dans `web/` ?
- **Granularité du canal** : par enseigne (« Auchan », « Leclerc ») ou par type
  (« un drive ») ? La mémoire d'habitude n'a pas le même sens dans les deux.
- **Seuil d'apprentissage** de D.19 : combien de tours cohérents avant qu'une
  attribution devienne une règle ?
- **Offline de E.26** : tolérance réelle exigée, ou hypothèse de confort ?
