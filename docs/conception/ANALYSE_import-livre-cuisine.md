# Importer un livre de cuisine photographié — analyse

Source de l'analyse : 13 photos de doubles pages d'un livre de recettes au fromage
(Brocciu, Maroilles, Époisses, Mont d'Or, Chaource, Neufchâtel, Rigotte de Condrieu,
Tome des Bauges, Pouligny-Saint-Pierre, Roquefort, raclette, Coulommiers).

**Cadre d'usage** : alimentation d'un vault personnel. Le texte et les photos du livre
restent sous droit d'auteur — ils n'ont pas vocation à être republiés ni exposés par une
API publique. Cette contrainte oriente l'axe 2 (§ Isolation d'image).

---

## 1. Détecter, analyser, parser, classer

### Ce que le livre offre gratuitement : une maquette régulière

Les 13 pages observées partagent la même anatomie, dans le même ordre :

| Zone | Contenu | Exemple |
|---|---|---|
| Titre | capitales, 1 à 3 lignes, **hiérarchisées** | `GROS CHAMPIGNONS` / `RÔTIS AU MAROILLES` |
| Temps | ligne unique, séparateurs `·` | `PRÉPARATION : 20 MIN · CUISSON : 20 MIN` |
| Rendement | en tête de colonne gauche | `POUR 4 PERSONNES` |
| Ingrédients | colonne gauche, **alignés à droite**, sans puce | `200 g de maroilles` |
| Étapes | colonne droite, paragraphes **non numérotés** | `Préchauffez le four à 220 °C.` |
| Pied de page | numéro + **catégorie** | `130  Plat` |

Trois conséquences directes :

- **La catégorie est donnée, pas à deviner** — `Entrée` / `Plat` / `Dessert` en pied de
  page alimente `recipe_type`/`family` sans heuristique.
- **Les sous-sections existent déjà** — `Pour la farce`, `Pour la sauce`, `Pour la pâte`,
  `Pour la garniture`, `Pour le mont d'or`. C'est **exactement** la structure qui a vidé
  5 recettes du vault (#58) : le modèle la supporte désormais, il faut juste la mapper sur
  des `###`.
- ⚠️ **Le rendement n'est pas toujours un nombre de personnes** :
  `POUR 4 PERSONNES`, `POUR 6-8 PERSONNES`, `POUR UNE TRENTAINE DE BISCUITS`,
  `POUR 4 FOCCACINE`. Voir § 3, c'est un piège à macros.

### Stratégie : vision LLM en amont, parser existant en aval

**Ne pas faire d'OCR brut suivi de regex.** Le titre est en display letter-spacé, la
colonne d'ingrédients est alignée à droite, et les photos sont prises de biais : un
tesseract naïf rend une soupe. Deux étages :

- **Étage A — lecture** : le modèle vision (Gemini, déjà câblé côté recipe-manager avec sa
  clé en credstore) reçoit l'image de page et rend un JSON calqué sur le schéma existant.
- **Étage B — structuration** : les lignes d'ingrédients obtenues repassent par
  **`parse_ingredient()`**, tel quel. Le livre écrit `3 ½ c. à s. de miel`,
  `½ neufchâtel`, `1 c. à c. de cumin torréfié`, `4 c. à s. de granola` — c'est déjà la
  grammaire que le parser gère (fractions typographiques, `c. à s.`, article `de`/`d'`).

L'intérêt de couper en deux : **ne pas écrire un second parser d'ingrédients**. Un modèle
qui rend directement `{qty, unit, name}` déplace la logique métier chez un fournisseur
tiers, non testable et dérivant à chaque version de modèle.

### Garde-fou

Même doctrine que partout ici : conserver `raw`, marquer `parsed=False`, ne jamais avaler
une ligne en silence. Un modèle vision hallucine des quantités plausibles — la parade
n'est pas la confiance, c'est l'écran de relecture (§ 6).

---

## 2. Isolation d'image malgré les pages arrondies

C'est l'axe le plus coûteux, et **le plus facile à contourner**.

### Ce que montrent les photos

Courbure près du pli, perspective (prise à main levée, de biais), ombres portées, pouce
dans le cadre, fond de table en bois, reflets. Un crop rectangulaire échoue : la photo est
à fond perdu et la page est à la fois courbée et trapézoïdale.

### Trois niveaux, par coût croissant

**a. Ne pas isoler du tout — recommandé pour la v1.**
La page entière part au modèle vision (qui lit très bien de biais), et l'illustration du
plat vient de **`POST /recipes/{slug}/generate-image`** (recipe-manager, prompt v1.1).
Aucun dewarping, aucune reproduction de la photographie du livre, et surtout : le parc
photo garde son unité visuelle. C'est déjà la doctrine inscrite dans CLAUDE.md — un
fichier local par recette, un seul prompt, une seule famille d'images.

**b. Redressement perspectif** — détection du plus grand quadrilatère (page), homographie
4 points, OpenCV suffit. Corrige le trapèze, **pas** la courbure du pli. Acceptable quand
la photo cible occupe presque toute la page opposée, ce qui est le cas courant ici.

**c. Dewarping cylindrique** — modèle de courbure de page. Vrai chantier, gain marginal
pour cet usage.

### Le vrai levier est à la prise de vue, pas en post-traitement

Page maintenue à plat, appareil parallèle, lumière rasante évitée — ou simplement une app
de scan du téléphone, qui redresse déjà. Corriger à la capture coûte dix secondes et
supprime l'essentiel du problème.

---

## 3. Calcul des macros

### Constat de départ : rien ne calcule aujourd'hui

- `recipe.macros_kcal` / `macros_protein` / `macros_carbs` / `macros_fat` sont **déclarées
  dans le frontmatter** du vault, à la main. `protein_density` en est dérivée
  (`normalizer.py::_compute_protein_density`).
- La seule donnée nutritionnelle **par aliment** du système est
  `shopping_product.nutrition` (JSONB) — elle vient d'Auchan et n'existe que pour un
  produit **effectivement acheté**.

Une recette de livre arrive donc avec zéro macro, et rien dans le système ne sait les
produire à partir d'une liste d'ingrédients.

### Trois voies

| Voie | Couverture | Coût | Verdict |
|---|---|---|---|
| **CIQUAL** (table ANSES, ~3 000 aliments, libre) | tout le catalogue, y compris les 56 recettes existantes | mapping `name_normalized` → code CIQUAL | **la bonne cible** |
| `shopping_product.nutrition` | seulement ce qui est passé par un drive | quasi nul | complément, pas socle |
| Estimation LLM | totale | nul | ❌ comme source primaire |

La voie CIQUAL rejoue exactement le problème d'appariement du garde-manger, avec le même
mode de défaillance : **un mauvais match ne se voit pas**, il produit un nombre faux avec
l'aplomb d'un nombre juste. Mêmes parades : ne jamais sur-normaliser, stocker le code
apparié et le score, exposer les non-appariés.

Une estimation LLM reste tolérable **si elle est stockée comme telle** (`source:
"estimated"`) et affichée comme telle. Un chiffre estimé qui ressemble à un chiffre mesuré
est pire que pas de chiffre.

### ⚠️ Le piège du rendement

`POUR UNE TRENTAINE DE BISCUITS` et `POUR 4 FOCCACINE` ne sont pas des portions. Diviser
par 4 quand le 4 compte des foccacine donne une macro par personne fausse — et crédible.

**Conséquence de modèle** : stocker `yield_qty` + `yield_unit` (`personne`, `biscuit`,
`foccacine`, `pot`), pas un `servings` entier. Et n'exposer une macro *par personne* que
lorsque `yield_unit == "personne"`.

---

## 4. Proposition de substitution pescétarienne

### Ce qui existe

`convives.py` porte `DIETS` et `check_meal()`, qui détecte les conflits par correspondance
de termes. Le pipeline est en place ; ce qui change, c'est sa **matière première**.

### Diagnostic sur ce livre

Julien a raison sur le fond : c'est un livre de fromages, donc majoritairement
lacto-végétarien. Sur les 13 pages vues, **3 posent réellement problème** :

| Recette | Ingrédient bloquant | Piste |
|---|---|---|
| Gros champignons rôtis au maroilles | 8 tranches de lard fumé | lard fumé végétal, ou suppression + noisettes concassées pour le gras et le croquant |
| Mont d'or à la bière | 16 tranches de lard | idem — le lard y est un enrobage, pas une structure |
| Croissants farcis tome des Bauges | 4 tranches de jambon blanc | suppression simple ; la béchamel porte le liant |

Plus, hors recettes, la planche « idées à emporter » (viande des Grisons, jambon cru).

### Le cas qui compte le plus : les anchois

La salade de haricots verts contient **6 anchois à l'huile**. Une règle naïve
« poisson = conflit » la bloquerait à tort : l'anchois est **compatible pescétarien**.
C'est le mode de défaillance à surveiller — le sur-blocage, qui fait rejeter des recettes
mangeables et érode la confiance dans l'outil plus vite qu'un oubli.

### Amélioration structurelle

`check_meal()` travaille aujourd'hui sur le **texte de description** du repas. Dès lors que
les ingrédients sont parsés en lignes, le contrôle doit porter sur
`recipe_ingredient.name_normalized` : plus précis, et débarrassé des faux positifs de
sous-chaîne. Les substitutions retenues se rangent dans `applied_substitutions`, déjà
présent sur le modèle.

---

## 5. Endpoints à créer

### Décision d'architecture : côté recipe-manager, pas CM2

recipe-manager **possède déjà** le modèle recette, la clé Gemini en credstore et
`generate-image`. Un second appelant Gemini dans CM2 dupliquerait le credential et
scinderait la propriété du modèle.

| Endpoint | Repo | Rôle |
|---|---|---|
| `POST /recipes/import/page` | recipe-manager | image(s) multipart → **brouillon** JSON. N'écrit rien. |
| `GET /recipes/import/drafts` | recipe-manager | brouillons en attente de validation |
| `PATCH /recipes/import/drafts/{id}` | recipe-manager | corrections humaines |
| `POST /recipes/import/commit` | recipe-manager | brouillon validé → écriture |
| `POST /api/recipes/import` | CM2 | façade pour le front + écran de relecture |

### ⚠️ La cible d'écriture est le `.md` du vault, pas la DB

Pour les recettes, **le vault fait foi** : `POST /api/ingest` remplace intégralement
ingrédients et étapes à chaque passage. Une recette écrite directement en DB serait effacée
à la première ingestion, sans erreur — le même silence que le `DELETE FROM menu` d'origine.

Le brouillon doit donc être **persisté** : la capture se fait debout, dans une librairie ou
une cuisine ; la validation se fait plus tard, assis. Sans persistance, l'import n'aboutit
que si les deux gestes tiennent dans la même minute.

---

## 6. UI à créer

### La contrainte qui décide de tout

**iPad mini 2 / Safari 12.5, en cuisine.** Elle tranche d'emblée :

- **Capture** : `<input type="file" accept="image/*" capture>` ouvre l'appareil natif et
  fonctionne. Ne pas compter sur `getUserMedia` (même famille de limite que
  MediaRecorder, qui a déjà imposé de masquer le FAB micro sur cet appareil).
- **Rendu** : pas de `<dialog>` → vue plein écran routée ; pas de `gap` en flex → grid ;
  pas d'`aspect-ratio` → `padding-bottom`. Mêmes parades que le reste du front, vérifiées
  par le gate iOS 12.

### L'écran qui porte tout : la relecture avant commit

Trois zones :

1. **la photo de page**, zoomable — c'est la référence, elle doit rester lisible ;
2. **les champs interprétés**, éditables (titre, temps, rendement, catégorie) ;
3. **« ce que j'ai compris »** — la liste des ingrédients, où **chaque ligne
   `parsed=False` est signalée visuellement**.

Cette troisième zone n'est pas une commodité : c'est la mise en écran d'une doctrine déjà
écrite dans `ingredients.py` — *« une quantité non comprise doit se voir à l'écran, jamais
disparaître — un ingrédient avalé en silence, c'est un achat manqué qu'on découvre en
cuisine »*.

Ajouter un **compteur de brouillons en attente**, visible depuis l'accueil : une recette
photographiée puis jamais validée est le mode d'échec le plus probable de toute la chaîne.

---

## Séquencement proposé

| Ordre | Axe | Pourquoi là |
|---|---|---|
| 1 | **1 + 5 + 6** | boucle complète et utilisable : photographier → relire → écrire |
| 2 | **4** substitutions | petit, une fois les ingrédients structurés |
| 3 | **3** macros (CIQUAL) | le plus gros morceau, et il profite aux 56 recettes existantes |
| — | **2** isolation d'image | **délibérément reporté** — les photos générées font le travail |

L'axe 2 est le seul dont le coût est sans rapport avec le bénéfice, parce qu'une parade
gratuite existe déjà dans le projet.

**Volumétrie** : 13 doubles pages photographiées ici. Un livre complet représente environ
une centaine de recettes, soit autant de captures — l'écran de relecture doit supporter la
répétition, pas seulement le cas unitaire.
