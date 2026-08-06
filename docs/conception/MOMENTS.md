---
title: Moments d'usage — Cooking Manager
axis: usage
proof_level: provisional
upstream: [../marque/STAKEHOLDERS.md]
downstream: [julien-test-case-design]
status: draft
date: 2026-08-06
---

# Moments d'usage

> Un moment ne décore pas : il produit les scénarios de test. Chaque moment porte la famille de
> scénarios qu'il engendre. Un moment sans scénario saute.

Le foyer compte quatre personnes, mais **Julien porte sept casquettes dans la même journée**. Un
persona « Julien, 43 ans » ne discrimine aucune décision d'écran ; le `role` à cet instant, si.
Chaque moment = `role` × situation × **contrainte matérielle**.

## Les sept rôles (casquettes), et leur moment

### R1. Le planificateur — le dimanche, au calme
> *Quand je prépare la semaine le dimanche, je veux composer un menu qui respecte les contraintes
> de chaque convive, afin de ne pas découvrir un conflit au moment de cuisiner.*
- **Situation/contrainte** : assis, au calme, vue d'ensemble ; a besoin de voir les conflits **avant**.
- **Famille de scénarios** : `conflit-detecté`, `convive-absent`, `menu-sans-option-pour-X`.
- **Scénario ajouté (2026-08-06)** : `ajout-convive-ponctuel` — « 5 personnes pour le gratin
  mercredi soir » → ajuster le nombre de convives **par repas**, pas globalement.

### R2. L'acheteur — le lundi, sur le drive
> *Quand je commande les courses, je veux la liste agrégée par les quantités réelles (convives ×
> portions), afin de ne pas racheter ce que le placard contient déjà.*
- **Contrainte** : passe par le drive Auchan ; le garde-manger doit être à jour.
- **Famille** : `agrégation-portions`, `différentiel-garde-manger`, `acheter-du-miel-qu-on-avait-déjà`.
- **Scénario ajouté (2026-08-06)** : `achat-manqué` — « on n'a pas acheté la mozzarella ni les
  champignons » → signaler un manque, l'app remonte l'impact sur les repas à venir et propose
  substitution ou changement de recette.
- **Scénario ajouté (2026-08-06)** : `ingredients-restants-semaine` — « qu'est-ce qu'il me faut
  encore ? » → vue agrégée de tous les ingrédients des repas restants (aujourd'hui → fin de semaine)
  moins le stock déclaré.

### R3. Le cuisinier — le soir, mains grasses, iPad à 60 cm
> *Quand je cuisine le soir, je veux suivre la recette sans toucher l'écran, afin de ne pas
> salir ni perdre ma place.*
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
> *Quand je range les courses ou que je constate un manque, je veux mettre à jour ce qui reste,
> afin que la planification et l'achat suivants partent du vrai stock.*
- **Famille** : `màj-garde-manger`, `péremption`, `stock-négatif-impossible`.
- **Scénario ajouté (2026-08-06)** : `rupture-stock` — « plus de skyr, on a fini le fromage
  blanc » → déclarer un ingrédient épuisé (vocalement ou via la vue garde-manger). L'app
  recalcule les impacts : quels repas cette semaine en dépendent ? Propose substitution ou
  changement de recette.
- **Scénario ajouté (2026-08-06)** : `garde-manger-reactif` — quand un ingrédient passe à zéro,
  les recettes impactées lèvent une alerte visible sur la vue menu (pas un email, pas un push :
  un signal sur l'écran que l'intendant a déjà sous les yeux).

### R6. Le préparateur — la veille au soir *(nouveau, 2026-08-06)*
> *Quand je range la cuisine après le dîner, je veux savoir ce que je dois préparer pour demain
> (overnight oats, décongeler, mariner), afin de ne pas me retrouver sans petit-déjeuner le matin.*
- **Situation/contrainte** : fin de journée, fatigue, besoin d'une réponse directe (« fais ça ce
  soir, c'est tout »). Le canal vocal est naturel ici : « que dois-je préparer ce soir pour
  demain ? »
- **Famille** : `prep-oubliee`, `decongelation-j-1`, `marinade-anticipee`.
- **Source de données** : chaque recette peut déclarer des **prep tasks** avec un délai relatif
  (veille au soir, matin même). L'app dérive un checklist « ce soir, prépare : » depuis le
  menu de demain.
- **Validation** : ce moment n'est dans aucune des 23 apps analysées (veille 2026-08-05). La
  raison : il suppose un lien recette → tâches de préparation temporisées, que personne ne
  structure.

### R7. Le compositeur — le samedi, envie spontanée *(nouveau, 2026-08-06)*
> *Quand j'ai envie de faire une recette en plus (le week-end, un invité surprise), je veux
> chercher une recette et que l'app optimise la liste de courses en fonction de ce qui reste
> au garde-manger, afin de n'acheter que le delta.*
- **Situation/contrainte** : hors du cycle planifié (dimanche → vendredi). La semaine est finie
  mais la cuisine continue. Le planificateur R1 travaille sur la semaine ; le compositeur
  travaille sur un repas isolé.
- **Famille** : `recette-hors-menu`, `delta-courses`, `repas-improvise`.
- **Journey associée** : recherche recette → l'app croise les ingrédients avec le stock →
  affiche ce qu'il faut acheter (et seulement ça).

## Journeys

### J1. La semaine planifiée (journey principale)

```
R1 Planifier (dimanche)
 → R2 Acheter (lundi)
   → R5 Ranger / stocker (lundi soir)
     → R6 Préparer la veille (chaque soir)
       → R3 Cuisiner (le jour même)
         → R4 Manger / donner son avis (à table)
           → R5 Mettre à jour le stock ("plus de skyr")
             → boucle R6 (soir suivant)
```

**Coupures identifiées (2026-08-06)** :
- Entre R2 et R3 : le stock n'est pas suivi en temps réel → un achat manqué ne remonte pas.
- R6 est entièrement absent : aucune visibilité sur les préparations anticipées.
- R5 → R2 (boucle retour) : une rupture déclarée en milieu de semaine ne recalcule pas les
  impacts sur les repas à venir.

### J2. Le repas improvisé (journey secondaire)

```
R7 Envie d'une recette → recherche
 → App croise ingrédients × stock
   → Delta courses (que le manquant)
     → R2 Acheter le delta
       → R3 Cuisiner
```

### J3. L'instanciation autonome (journey tertiaire)

Aujourd'hui, créer un menu / ajouter une recette / gérer les convives passe par Claude Code
ou par l'édition directe du vault Obsidian. **L'app doit offrir une UX d'instanciation** :
- Créer / modifier un menu directement dans l'app (pas seulement le lire)
- Ajouter une recette depuis une URL (parseur) ou en saisie libre
- Gérer les convives et leurs contraintes (écran dédié)
- Gérer les présences (qui mange quand)

### J4. L'import de recette (journey transverse)

```
Utilisateur trouve une recette (web, livre, ami)
 → Colle une URL ou dicte le texte
   → Parseur extrait : titre, ingrédients, étapes, portions, temps
     → Normalisation FR (unités, termes)
       → Fiche recette créée dans le vault
         → Disponible pour planification R1 et composition R7
```

**Contrainte** : le parseur doit être spécialisé sur les recettes françaises (unités « c.à.s »,
« verre de », « un filet de ») tout en sachant lire et traduire les recettes anglaises à la
volée. Potentiellement un package partagé entre Cooking Manager et Waaker.

## Anti-usage (à qui / à quand on ne s'adresse pas)

- **Le cuisinier d'inspiration** qui n'aime pas planifier : un réseau de recettes le sert mieux.
- **Le foyer sans contrainte alimentaire** : le cœur du produit (la détection de conflits) ne lui
  sert à rien — l'optimiser pour lui dilue le seul terrain où l'on gagne.

## Reste à trancher (avec Julien et Clémence, pas dérivable)

- **Le canal du geste** de R3 (mains grasses, iPad à distance).
- **Qui porte réellement quel rôle** — R1 à R7 sont attribués à Julien par défaut ; à confirmer.
- **Granularité du garde-manger** : par ingrédient générique (« skyr ») ou par produit acheté
  (« Skyr Danone 450g ») ? Le premier est plus simple à tenir, le second permet le delta courses.
- **Prep tasks dans les recettes** : champ structuré dans le frontmatter (ex. `prep: [{task: "décongeler crevettes", delay: "J-1 soir"}]`) ou dérivé du corps par LLM ?
