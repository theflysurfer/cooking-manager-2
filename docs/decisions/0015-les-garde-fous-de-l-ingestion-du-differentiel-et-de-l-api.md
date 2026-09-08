# 0015 — Les garde-fous de l'ingestion, du différentiel et de l'API

- **Statut** : accepté
- **Date** : 2026-09-08
- **Porte** : `backend/ingest.py`, `backend/app.py`, `cooking_manager/pantry.py`, `presence.py`
- **Issues** : #58, #71, #76
- **Voir aussi** : ADR 0009 (du besoin de recette à la quantité d'achat), ADR 0010

## Contexte

Chacune des règles ci-dessous a été écrite après un incident daté. Elles vivaient
en commentaires, à côté du code qu'elles protégeaient — donc invérifiables, et
promises à devenir fausses sans erreur.

## Décision — l'ingestion

### 1. L'appariement menu ↔ fiche joue dans les DEUX SENS, avec un seuil

La fiche est souvent plus détaillée que l'intitulé du menu : « Wraps poulet froid
+ crudités » au menu, « … + ranch skyr » en fiche. Ne tester qu'un sens laissait
ces repas orphelins, donc leurs ingrédients hors des courses.

Le seuil de **12 caractères sur la partie commune** empêche qu'un titre court
(« Œufs ») s'accroche à tout intitulé qui le mentionne.

### 2. Un slug qui ne pointe nulle part est une faute de frappe, pas une absence

Le dire, plutôt que retomber en silence sur un appariement approximatif. Un
`<slot>_slug` **désigne** la fiche et court-circuite toute heuristique : c'est la
seule liaison qui ne redérive pas, l'intitulé rédigé à la main chaque semaine
finissant toujours par diverger du titre de la fiche d'un mot ou deux.

### 3. Le garde-fou d'ingrédients ne voit pas le cas le plus grave

Un contrôle gardé par `content.ingredients` ne peut pas voir une section qui ne
rend **aucune** ligne. Ce trou a laissé 5 recettes sans le moindre ingrédient,
sans un mot dans les logs (#58) — et une liste de courses amputée ne se découvre
qu'en cuisine.

Corollaire : deux fichiers du vault qui déclarent le même slug se réduisent à un
seul par l'upsert. Le dire, sinon la fiche perdue n'existe nulle part.

### 4. Jamais de `DELETE FROM menu`

L'upsert par slug suffit à dédoublonner. Le DELETE détruisait tout menu absent du
vault, y compris ceux créés par l'API — incident du 2026-08-04, le menu « Semaine
du 3 au 7 août » effacé par une ingestion de recettes.

Symétriquement, ingrédients et étapes sont **remplacés en entier** à chaque
ingestion : le vault fait foi, et les positions changent dès qu'on réordonne une
liste.

### 5. `photo_url` est en COALESCE

C'est la seule colonne dont la valeur ne vient pas toujours du vault : sans
fichier local, elle est reconstruite à chaque ingestion par un scraping qui dépend
d'un site tiers joignable en 8 s. L'écrire sans condition efface la photo dès
qu'un scraping échoue — la grille du menu perdait ses images sans erreur ni trace.

## Décision — le différentiel garde-manger

### 6. La clé d'agrégation porte la FAMILLE D'UNITÉ, pas seulement le nom

« 2 courgettes » et « 200 g de courgettes » ne s'additionnent pas. Les fondre sous
une seule clé produit un chiffre faux qui a l'air juste, ou — pire — fait
disparaître la seconde quantité en silence.

Le **dénombrable est sa propre famille** : « 4 œufs » se compare bien à
« 6 pièces ». Sans cette entrée, tout ingrédient compté sortait en `inconnu` — la
moitié du frais, noyée en questions inutiles.

### 7. Ne pas poser une question qui n'en est pas une

Deux cas où `inconnu` serait du bruit :
- **besoin non chiffré** (« huile d'olive pour la poêle », « sel ») : avoir le
  produit suffit ;
- **besoin à l'échelle de la cuillère face à un contenant** (« 2 pots ») :
  personne ne manque d'une cuillère de miel quand il a deux pots.

Le raisonnement : une liste qu'on n'a plus envie de lire est **une liste qu'on
cesse de croire**. C'est le cas exact du miel et de la sauce soja rachetés le
2026-08-04.

### 8. Mais ne jamais conclure « suffisant » faute de pouvoir comparer

Quand une quantité est demandée et que la comparaison est impossible — unités
incommensurables, stock non chiffré — la réponse est `inconnu`. Conclure
« suffisant » est le faux positif qui fait sauter un achat, et il ne se découvre
qu'en cuisine.

`status = low` ne court-circuite pas la comparaison de quantités. Une fourchette
(« 2–3 c.s. ») s'achète au **maximum** : manquer coûte plus cher qu'avoir un peu
trop.

### 9. La date d'évaluation est un paramètre, jamais `date.today()`

La règle d'ancienneté est la déduction la plus lourde de conséquences du
différentiel : elle vide le frais d'un coup. **Une règle qu'on ne peut pas figer
dans un test est une règle qu'on ne peut pas défendre.** La péremption se *dit* au
lieu de se décider en coulisses : l'utilisateur doit pouvoir contredire.

## Décision — l'API

### 10. `EXISTS`, pas `JOIN`, pour filtrer le catalogue sur une semaine

Une recette refaite trois fois dans la semaine doit apparaître **une** fois dans
le catalogue. Le nombre de fois est une donnée de la recette (`occurrences`), pas
une multiplication des lignes.

Le calcul des quantités, lui, ne dédoublonne pas : une recette faite deux fois
pèse deux fois.

### 11. Les décimales s'arrondissent à la sortie de l'API

Les colonnes sont en `NUMERIC` et asyncpg rend des `Decimal`. La conversion et
l'arrondi se font une fois, à la frontière, pour que l'UI n'ait jamais à s'en
soucier : un ancien `REAL` ressortait en `3.799999952316284` et s'affichait tel
quel.

### 12. Une recette sans ingrédient parsé ne garantit RIEN

Le dire, plutôt que rendre « aucun conflit » — ce qui se lit comme une
compatibilité vérifiée. Même famille que les repas de restes, sans fiche par
conception (#76) : les compter comme manquants ferait clignoter une alerte qu'on
ne peut pas éteindre.

### 13. Le seed ne réimpose jamais les aversions

`dislikes`, `forbidden` et `diet_exceptions` sont posés à la **création** et
jamais réécrits : ils s'affinent à l'usage. Un seed qui les réimpose efface sans
un mot ce qui a été saisi depuis — Clémence en avait quatre que le seed ne connaît
pas.

### 14. Un séjour met ses membres à table, quelle que soit la trame

C'est le correctif du bug fondateur (F.30, Bègles) : une « absence » du foyer
principal ne doit plus vider la tablée quand la famille cuisine sur place.

### 15. L'import d'une page de livre est une façade

CM2 ne parle pas à Gemini : recipe-manager possède le modèle recette **et** la clé
en credstore. Un second appelant dupliquerait le credential et scinderait la
propriété du modèle. CM2 relaie, pour que le front n'ait qu'une origine à appeler
et pas de CORS à ouvrir — en relayant le code d'origine, car un 409 « fiche déjà
présente » ne doit pas se présenter comme une panne serveur.

## Décision — les deux principes fondateurs du domaine

### 16. Tolérance au parsing : une ligne qui résiste garde son `raw`

Toute ligne d'ingrédient que le parseur ne comprend pas conserve son texte
d'origine et **reste affichable telle quelle**. Une quantité non comprise doit se
voir à l'écran, jamais disparaître : un ingrédient avalé en silence est un achat
manqué qu'on découvre en cuisine.

C'est la même famille de raisonnement que `unresolved` côté macros et `inconnu`
côté différentiel. Le système a le droit de ne pas savoir ; il n'a pas le droit de
faire comme s'il savait.

### 17. Le contrôle de compatibilité ne repose pas sur la mémoire d'un humain

Incident fondateur, 2026-08-04 : le menu programmait « Wraps poulet froid » un
mardi midi alors que Clémence est **pescétarienne** — noté noir sur blanc dans le
vault depuis mai. Le vault documentait tout ; **rien ne l'ingérait**, la table
`convive` était vide, et l'app n'avait aucun moyen de le savoir.

Un seul repas de la semaine était en faute, et personne ne l'a vu. C'est ce qui
justifie que le contrôle soit exécuté et non recommandé, et qu'il préfère une
alerte à lever au silence (ADR 0013 §3).

## Conséquences

- Ces règles sont exécutées par le code et vérifiées par les tests. Cet ADR dit
  **pourquoi** elles existent ; il ne les remplace pas.
- Une règle renversée supersède cet ADR au lieu de le corriger.
