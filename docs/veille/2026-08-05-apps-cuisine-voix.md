---
title: "Veille concurrentielle — apps de cuisine, planification de menus et commande vocale"
version: 1
audience: interne
level: stratégique
status: draft
last_review: 2026-08-05
revisions:
  - date: 2026-08-05
    note: première passe, 23 acteurs analysés sur les 12 axes
---

# Veille concurrentielle — apps de cuisine et commande vocale

> **Verdict en une phrase** : le marché de la planification de repas est **dense** côté
> inspiration et courses. Le croisement contraintes alimentaires par convive × commande vocale ×
> recettes propres n'est couvert par **aucun** acteur trouvé — mais cette intersection est
> probablement **étroite par nature** (cf. § Contre-épreuve), pas oubliée par le marché.

## Axes de concurrence

Classement par job d'abord, technologie en dernier — conforme à `axes-de-concurrence.md`.

---

### Axe 1 — Job to be done

Le job de Cooking Manager n'est **pas** « trouver une recette ». C'est :

> **Savoir quoi manger ce soir sans friction, en tenant compte de ce que chaque personne à
> table peut et veut manger.**

Trois sous-jobs en découlent : planifier la semaine (R1), acheter le juste nécessaire (R2),
cuisiner sans toucher l'écran (R3).

| Acteur | Job principal | Recouvrement |
|---|---|---|
| **Jow** | « On te dit quoi manger et on remplit ton caddie » | R1 + R2 mais pas R3 |
| **Mealime** | Planifier des repas sains + liste de courses | R1 + R2 |
| **Plan to Eat** | Sauvegarder ses recettes + planifier + liste | R1 + R2 |
| **Eat This Much** | Remplir automatiquement un plan calorique | R1 (automatisé) |
| **Paprika** | Organiser sa collection de recettes | Consultatif, pas R1 |
| **Mealie** | Self-hosted recipe manager + meal plan | R1 + R2 (devops) |
| **Tandoor** | Self-hosted recipe + shopping + meal plan | R1 + R2 (devops) |
| **SideChef** | Guider pas-à-pas un cuisinier débutant | R3 uniquement |
| **Cookie** | Cuisiner mains-libres, voix-first | R3 uniquement |
| **Pestle** | Importer n'importe quelle recette + cuisiner | R3 + import |
| **Voicipe** | Rendre n'importe quel site cuisinable à la voix | R3 uniquement |
| **Honeydew** | Assistant IA cuisine (recettes, modif, gestes) | R3 + IA |
| **Grocy** | Gérer le stock alimentaire du foyer | R5 uniquement |
| **Marmiton** | Trouver de l'inspiration (base communautaire FR) | Hors job |
| **Cookpad** | Partager ses recettes en communauté | Hors job |
| **HelloFresh / Quitoque** | Ne plus décider (kit livré) | Anti-pattern de R1 |

✅ **Constat** : les planificateurs (Jow, Mealime, Plan to Eat) couvrent R1+R2 mais ignorent
R3. Les assistants cuisson (Cookie, Pestle, SideChef) couvrent R3 mais ignorent R1. Personne
ne porte R4 (appréciation attribuée) ni R5 (intendance du placard) couplés au planning.

---

### Axe 2 — Moment et lieu d'usage

| Moment (cf. MOMENTS.md) | Qui le couvre | Comment |
|---|---|---|
| R1 — dimanche, au calme, vue d'ensemble | Jow, Mealime, Plan to Eat, Eat This Much, Tandoor | Drag & drop de recettes dans un calendrier |
| R2 — lundi, drive, liste agrégée | Jow ✅ (panier direct), Mealime, Plan to Eat (liste) | Jow seul connecte au drive (Carrefour, Auchan…) |
| R3 — soir, mains grasses, iPad à 60 cm | Cookie, Pestle, Voicipe, SideChef, Honeydew | Voix et/ou gestes |
| R4 — à table, retour attribué | ❌ **Personne** | Aucune app ne trace l'appréciation **par convive** |
| R5 — devant le placard, mise à jour stock | Grocy, Tandoor (partiel) | Scan code-barres |

✅ **Constat** : R4 est un espace entièrement vide. R3 est couvert mais **jamais couplé** à
R1/R2 dans le même produit.

---

### Axe 3 — Usager

| Profil | Acteurs qui le ciblent |
|---|---|
| Parent gérant l'alimentation du foyer (contraintes) | **Aucun explicitement** |
| Personne qui veut manger sain (solo ou couple) | Mealime, Eat This Much, Yummly (†) |
| Cuisinier débutant qui veut être guidé | SideChef, HelloFresh |
| Cuisinier occupé, mains prises | Cookie, Pestle, Voicipe |
| Foodie / créateur de contenu | Cookpad, Marmiton, Tasty |
| Geek self-hosted | Mealie, Tandoor, Grocy |

⚠️ Le profil « parent qui gère un foyer avec des contraintes alimentaires **divergentes** »
n'est revendiqué par **aucun** acteur. Jow permet d'exclure des ingrédients (pour un seul
profil), pas de croiser les régimes de plusieurs convives pour le même repas.

---

### Axe 4 — Payeur

| Modèle | Acteurs |
|---|---|
| Gratuit (monétisation par les courses) | **Jow** (commission drive) |
| Freemium (base gratuite + premium) | Mealime, Paprika, Pestle, Honeydew (~4 €/mois) |
| Achat unique | Paprika (4,99 €), Plan to Eat |
| Abonnement | Eat This Much (8,99 $/mois), SideChef Pro, Mealime Pro |
| Kit livré (le repas EST le produit) | HelloFresh, Quitoque |
| Open source / self-hosted | Mealie, Tandoor, Grocy |
| Fermé / mort | Yummly (fermé déc. 2024) |

✅ Cooking Manager est gratuit, self-hosted, sans monétisation — pas en concurrence directe
sur le modèle économique. Le risque n'est pas le prix, c'est l'**effort d'adoption** (vault
Obsidian, PostgreSQL, VPS).

---

### Axe 5 — Prescripteur

| Prescripteur | Acteurs concernés |
|---|---|
| Le conjoint / les enfants (contraintes subies) | **Cooking Manager** (seul à le modéliser) |
| Le médecin / diététicien | Eat This Much (régimes médicaux), Mealime (filtres allergie) |
| L'influenceur / créateur de contenu | Tasty, Marmiton, Cookpad |
| Le distributeur alimentaire | Jow (partenariat Carrefour, Auchan, Leclerc) |

❓ Chez Cooking Manager, Clémence est prescriptrice sans être utilisatrice — un pattern que
personne d'autre ne modélise.

---

### Axe 6 — Canal

| Canal | Acteurs |
|---|---|
| App mobile native (iOS) | Pestle, Cookie, Honeydew, Mealime, Paprika, Jow |
| App mobile native (Android) | Voicipe, SideChef, Mealime, Paprika, Jow |
| Web app | Plan to Eat, Chef Cecil, Mealie, Tandoor |
| Smart display (Echo Show, Nest Hub) | SideChef, Allrecipes (†), Tasty |
| Enceinte connectée (Alexa, Google Home) | SideChef (voice skill) |
| **Web app ciblant un iPad posé en cuisine** | **Cooking Manager** (seul) |

⚠️ Le canal « web app sur tablette vieillissante en cuisine » est un angle mort du marché.
Les apps natives ciblent les derniers OS ; une web app qui tourne sur Safari 12 est un
choix défensif que personne ne fait.

---

### Axe 7 — Modèle économique

Couvert à l'axe 4. Rien à ajouter.

---

### Axe 8 — Origine du contenu

| Source | Acteurs | Conséquence |
|---|---|---|
| Éditorial (rédaction interne) | Jow, SideChef, HelloFresh, Tasty | Qualité contrôlée, mais pas *mes* recettes |
| Communautaire (UGC) | Marmiton, Cookpad, Allrecipes (†) | Volume, mais bruit et doublons |
| Import depuis le web | Pestle, Paprika, Cookie, Honeydew | Agrège sans posséder |
| **Vault personnel (Obsidian, markdown)** | **Cooking Manager** (seul) | Les recettes sont les nôtres, éditées à la main |
| Base auto-générée par IA | Honeydew, FoodiePrep | Risque de recettes « plausibles mais jamais testées » |

✅ Cooking Manager est le seul à lire depuis un **vault Obsidian personnel** comme source de
vérité. Ce n'est ni un avantage d'inspiration (catalogue restreint) ni un handicap (chaque
recette a été validée en cuisine). C'est un **choix d'autorité sur la donnée**.

---

### Axe 9 — Couverture

| Acteur | Taille du catalogue |
|---|---|
| Marmiton | ~90 000 recettes |
| Cookpad | >5 millions (global) |
| SideChef | ~18 000 |
| Jow | ~1 500 recettes (éditorial strict) |
| Pestle / Cookie | Le catalogue de l'utilisateur (import) |
| **Cooking Manager** | ~30 recettes (vault personnel, août 2026) |

⚠️ La couverture n'est **pas** un axe de compétition pour Cooking Manager — on ne cherche
pas l'inspiration, on gère le menu de la semaine avec nos propres recettes. Le comparer
par le nombre de recettes, c'est mesurer une bibliothèque privée à l'aune de Wikipedia.

---

### Axe 10 — Forme

| Forme | Acteurs |
|---|---|
| App native mobile-first | Jow, Mealime, Pestle, Cookie, Honeydew |
| Web app responsive | Mealie, Tandoor, Plan to Eat, **Cooking Manager** |
| Dashboard desktop | Grocy |
| CLI / API-first | Tandoor (API REST), **Cooking Manager** (FastAPI + curl) |
| Voice-first (pas d'écran) | Chef Cecil |

---

### Axe 11 — Degré de guidage

| Niveau | Acteurs |
|---|---|
| Catalogue passif (chercher, lire) | Marmiton, Cookpad, Paprika |
| Planification assistée (drag & drop) | Plan to Eat, Mealime |
| Planification automatique | Jow, Eat This Much |
| Guidage cuisson pas-à-pas | SideChef, Pestle, Cookie, HelloFresh |
| Guidage cuisson conversationnel (IA) | Honeydew, FoodiePrep, **Cooking Manager** (voice+LLM) |
| Exécution automatique (robot) | Upliance.ai |

✅ Cooking Manager est au niveau « conversationnel (IA) » pour R3, mais reste en
planification **manuelle** pour R1 — un choix délibéré (le menu est une décision humaine).

---

### Axe 12 — Technologie

| Technologie | Acteurs |
|---|---|
| Cloud propriétaire | Jow, Mealime, SideChef, HelloFresh |
| Self-hosted (Docker) | Mealie, Tandoor, Grocy |
| Self-hosted (systemd + VPS) | **Cooking Manager** |
| MediaRecorder + Deepgram + LLM cloud | **Cooking Manager** (seul dans cette combinaison) |
| Wake word propriétaire + STT | Cookie (« Cookie… »), Chef Cecil (« Hey Chef ») |
| Alexa / Google Assistant | SideChef, allrecipes (†) |
| Vision IA (photo → recette) | Samsung Food + Gemini, Honeydew |
| Gestes de la main / clignements | Pestle (caméra frontale), Honeydew |

---

## Analyse croisée : les combinaisons manquantes

Le marché est **saturé** sur « trouver une recette » et « faire une liste de courses ».
Il est **vide** sur les intersections :

| Combinaison | Acteur | Verdict |
|---|---|---|
| Planification + contraintes **par convive** | ❌ personne | **Espace vide** |
| Voix en cuisine + **ses propres recettes** (pas un catalogue) | ❌ personne | **Espace vide** |
| Retour attribué **par personne** sur un plat | ❌ personne | **Espace vide** |
| Panneau transcript + intent (transparence IA vocale) | ❌ personne | **Première** |
| Planification + courses drive + cuisson vocale (R1→R3) | ❌ personne | **Espace vide** — Jow fait R1+R2, Cookie fait R3, personne ne fait R1+R2+R3 |
| Source = vault Obsidian | ❌ personne | **Niche assumée** |

---

## Teardown des 5 acteurs les plus proches

### 1. Jow — le plus proche sur R1+R2

- **Ce qu'il fait bien** : planification automatique → panier drive en un clic. UX
  redoutablement simple. Intégration Auchan, Carrefour, Leclerc. Contenu éditorial de
  qualité (recettes testées, portions calibrées).
- **Ce qu'il ne fait pas** : aucune gestion de contraintes par convive (un seul profil
  « le foyer »). Pas de cuisson guidée. Pas de voix. Les recettes ne sont pas les nôtres.
- **Modèle** : gratuit (commission sur les courses). ⚠️ Dépendance au partenariat distributeur.
- **À retenir** : son onboarding (quiz préférences → menu auto) est le benchmark de la
  friction zéro sur R1. *(Reverse UX détaillé dans `data/ux-reverse-jow-2026-08-04.json`.)*

### 2. Cookie — le plus proche sur R3

- **Ce qu'il fait bien** : voix-first *sans* wake word dédié pour les commandes simples.
  Import depuis 1000+ sites. Timers multiples. Fonctionne offline. Confirmation haptique.
- **Ce qu'il ne fait pas** : pas de planification. Pas de courses. Pas de contraintes.
  iOS uniquement. Pas de vue hebdomadaire du menu.
- **À retenir** : la confirmation haptique après chaque commande vocale (pas seulement
  visuelle). Le mode offline.

### 3. Pestle — R3 avec le meilleur import

- **Ce qu'il fait bien** : import de recette depuis **n'importe quelle URL** (scraping +
  parsing structuré). Navigation par geste de la caméra frontale (wave-to-advance). SharePlay.
  Intégration Apple Intelligence (iOS 26).
- **Ce qu'il ne fait pas** : pas de planification. Pas de courses. iOS uniquement.
- **À retenir** : le geste caméra comme alternative à la voix en milieu bruyant. L'import
  universel.

### 4. Mealie — le plus proche en architecture

- **Ce qu'il fait bien** : self-hosted, API REST, meal planner + shopping list. Docker
  one-click. Import depuis Paprika/Tandoor/Chowdown. Multi-utilisateur avec permissions.
- **Ce qu'il ne fait pas** : pas de contraintes par convive. Pas de voix. Pas de connexion
  drive. UI orientée desktop.
- **À retenir** : le modèle d'import multi-source et l'API REST bien documentée.

### 5. Honeydew — le plus avancé en IA cuisine

- **Ce qu'il fait bien** : assistant IA « Ask Honey » conversationnel pendant la cuisson.
  Import vidéo (TikTok/Instagram/YouTube → recette structurée). Gestes de la main ET
  clignements. Modification de recette à la volée (« sans gluten », « moins calorique »).
- **Ce qu'il ne fait pas** : pas de planification hebdomadaire. Pas de gestion de foyer
  multi-convives. ~4 €/mois. Pas de source personnelle.
- **À retenir** : le pipeline vidéo → recette est impressionnant. L'IA modifie les
  recettes en contexte (pas juste des commandes, des conversations).

---

## Contre-épreuve : pourquoi personne ne le fait ?

Conclure à un « espace vide » est le résultat qu'on a envie de croire. Avant de s'y
installer, il faut expliquer **pourquoi** l'espace est vide — un espace peut être vide
parce que personne n'y a pensé, ou parce que personne n'en veut.

**Hypothèses sur l'absence de contraintes multi-convives :**

1. ⚠️ **Le marché vise les individus, pas les foyers.** Les apps de meal planning sont
   nées dans l'écosystème fitness/santé (MyFitnessPal → Mealime → Eat This Much) où
   l'unité est la personne, pas la tablée. Ajouter des profils multiples complique l'UX
   pour un cas d'usage minoritaire (les foyers avec contraintes *divergentes*).

2. ⚠️ **Les kits livrés contournent le problème.** HelloFresh et Quitoque éliminent la
   planification ET les courses : si le kit arrive avec ses ingrédients, les contraintes
   par convive se gèrent en amont (au choix du menu kit). Le segment
   « je-ne-veux-plus-décider » est plus gros que « je-veux-mieux-décider ».

3. ❓ **La taille du marché est peut-être petite.** Un foyer de 4+ personnes avec des
   contraintes alimentaires divergentes ET un parent qui veut optimiser ça dans une app
   — combien sont-ils ? Jow (>3M utilisateurs FR) ne l'a pas ajouté en 5 ans. Soit ils
   n'y ont pas pensé, soit la demande est trop faible pour justifier la complexité.

4. ❓ **Le problème se résout autrement.** Beaucoup de foyers gèrent les contraintes par
   la conversation (« qu'est-ce qu'on mange ce soir ? ») et non par un outil. Le coût
   d'adoption d'une app est supérieur au coût de la question posée à table.

**Ce que ça implique** : notre avantage n'est un avantage que si le foyer ciblé (a) a des
contraintes divergentes réelles, (b) planifie à la semaine (pas au jour le jour), et
(c) cuisine à partir de ses propres recettes. Ce profil existe — c'est le nôtre — mais
il n'est pas universel. L'espace est vide par **étroitesse de la niche**, pas par oubli
du marché.

**Vérification stores et forums :**

- ✅ **App Store (recherche « meal plan family allergies »)** : Mealime et Eat This Much
  apparaissent. Aucun ne mentionne « per-person » ou « per-family-member » dans sa fiche.
  Avis 1-2 étoiles de Mealime (triés récents) : plusieurs demandent « my husband is
  allergic to X but I'm not, I can't set different profiles » — la demande existe,
  la fonctionnalité non.
- ✅ **Reddit r/mealprep, r/EatCheapAndHealthy** : posts récurrents « how do you meal plan
  for a family with different dietary needs? ». Réponses : tableurs, Notion, « I just cook
  two versions ». Aucune app citée.
- ⚠️ **Forum Marmiton** : pas de fonctionnalité de planification, donc pas de demande
  multi-convive. Hors scope.

**Conclusion nuancée** : la demande existe (avis stores, Reddit) mais elle est niche et mal
servie — pas « personne n'y a pensé » mais « le ROI n'a pas justifié la complexité pour les
apps grand public ». Notre position est celle d'un **outil de niche fait pour le cas exact
qu'on vit**, pas une disruption d'un marché de masse.

---

## Ce que ça change pour Cooking Manager

### À prendre

1. **La confirmation haptique** de Cookie — vibrer après une commande vocale reconnue, en
   plus du panneau visuel.
2. **Le geste caméra** de Pestle — alternative à la voix quand la hotte couvre tout. Mais
   attention : l'iPad mini 2 n'a pas l'API pour ça.
3. **L'onboarding quiz** de Jow — pas pour la planification (notre menu est manuel), mais
   pour initialiser les contraintes des convives au premier lancement.

### À ne pas prendre

1. **La planification automatique** (Jow, Eat This Much) — le menu est une décision humaine
   chez nous. Automatiser = perdre le seul moment où Julien anticipe les conflits.
2. **Le catalogue éditorial** — nos recettes sont les nôtres. Ajouter des suggestions
   « inspirantes » dilue le terrain (contraintes par convive) où l'on gagne.
3. **L'import vidéo IA** (Honeydew) — génère des recettes « plausibles mais jamais testées
   en famille ». Incompatible avec le principe d'autorité du vault.

### Ce qu'ils n'ont pas et que nous avons

1. **Contraintes croisées par convive** — le cœur : Clémence ne mange pas de poulet, Léa
   refuse l'œuf dur, le même repas doit satisfaire les deux. Personne ne le fait.
2. **Appréciation attribuée** (R4) — « Titouan a aimé, Léa non ». Pas une moyenne de foyer.
3. **Panneau transcript + intent** — transparence du pipeline vocal. Aucune app cuisine ne
   montre ce que le système a compris et l'action qu'il va exécuter. Pattern issu du
   tooling de dev (Dialogflow), jamais porté au consumer.
4. **Source = vault Obsidian** — les recettes sont des fichiers markdown versionnés, pas une
   base propriétaire. Portabilité totale.
5. **Chaîne R1→R2→R3 dans un seul produit** — planifier → acheter (Auchan Drive) → cuisiner
   à la voix. Jow fait R1+R2, Cookie fait R3, personne ne fait les trois.

---

## Angles morts assumés

Ce que cette veille n'a **pas** cherché et pourquoi :

- ❓ **Apps asiatiques** (Cookpad JP, Xiachufang, Meishijie) : marché CJK, pas transférable
  au foyer français. Peuvent avoir des innovations non vues.
- ❓ **Appareils connectés** (Thermomix, KitchenAid avec écran intégré) : hardware captif,
  pas comparable à une web app sur iPad. Mais le Thermomix TM6 a un écran tactile avec
  guidage pas-à-pas et pourrait ajouter de la voix.
- ❓ **Apps de régime médical** (Lifesum, MyFitnessPal, Noom) : même si elles gèrent des
  restrictions alimentaires, leur job est « perdre du poids », pas « nourrir un foyer ».
  Possible recouvrement si elles ajoutent un mode multi-profil.
- ❓ **Projets open source confidentiels** sur GitHub : une recherche « recipe manager
  dietary constraints per person » pourrait révéler des prototypes non référencés.
- ⚠️ **Google Nest Hub cookbook** : supprimé en 2024 par Google. L'historique de cette
  fonctionnalité (et les raisons de sa suppression) n'a pas été fouillé.
- ⚠️ **Brevets** : aucune recherche de brevets sur « multi-person dietary constraint
  meal planning ». Un brevet dormant ne change rien au produit, mais changerait une
  éventuelle commercialisation.
- ⚠️ **Avis App Store en langues non-FR/EN** : seuls les avis en français et anglais
  ont été consultés. Des apps régionales (Cookpad JP, Meishijie CN) peuvent avoir
  des fonctionnalités non documentées en anglais.

---

## Recherche par axes croisés (traçabilité des requêtes)

| Passe | Requête | Résultats notables |
|---|---|---|
| JOB | "app meal planning dietary restrictions per family member" | ❌ Aucun résultat pertinent — toutes les apps gèrent UN profil |
| JOB | "cooking app voice commands hands free" | Cookie, Pestle, SideChef, Voicipe, Chef Cecil |
| JOB | "recipe app show transcript voice intent" | ❌ Aucun — pattern inexistant |
| CLIENT | "app cuisine familiale contraintes alimentaires" | Jow (un profil), Mealime (filtres) — aucun multi-convive |
| CLIENT | "self-hosted recipe manager meal plan" | Mealie, Tandoor |
| CLIENT | "cooking app feedback per person attribution" | ❌ Aucun |
| TECHNO | "deepgram cooking app" | ❌ Aucun (Deepgram en santé et transcription de réunion) |
| TECHNO | "obsidian recipe vault cooking" | Quelques templates Obsidian, pas d'app connectée |
| TECHNO | "LLM voice cooking assistant 2025 2026" | Honeydew, FoodiePrep, Samsung Food + Gemini |

**Test d'angle mort** : « Un produit qui fait le même job (nourrir un foyer en croisant les
contraintes de chaque convive) sans partager notre technologie (Obsidian, FastAPI, Deepgram),
quelle requête l'aurait trouvé ? » → « family meal planner allergies per person ». Résultat :
Mealime (un profil), Yummly (fermé). Toujours pas de multi-convive.

---

*Marqueurs de certitude : ✅ = lu sur la page citée · ⚠️ = rapporté, non recoupé ·
❓ = déduit ou extrapolé*
