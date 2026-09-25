---
numero: 0037
titre: Une part de convive est une donnée, pas une parenthèse
statut: accepté
date: 2026-09-25
concerne:
  - cooking_manager/parts.py
  - cooking_manager/convives.py
  - backend/db.py
  - backend/ingest.py
  - backend/app.py
issue: 159
supersede_partiellement: 0025
---

# 0037 — Une part de convive est une donnée, pas une parenthèse

## Contexte

Une part séparée — la portion d'un plat préparée pour un convive dont le régime refuse
l'ingrédient principal — ne vivait que dans le **texte** de la ligne d'ingrédient :
`150 g crevettes décortiquées (part Clémence)`. `recipe_ingredient` n'avait aucun champ de
convive, donc `/compatibility` ne pouvait pas savoir que la viande ne la concernait pas.

Mesuré en base le 2026-09-25 : **20 fiches** citent Clémence dans leur `body`, mais seulement
**8 lignes d'ingrédient** contiennent le mot « part », dont **3 faux positifs**
(« servi à part, jamais mêlé », « pour 3 parts carnées »). Trois orthographes coexistaient :
`(part Clémence)`, `(part de Clémence)`, `(surgelé, pour Clémence)`. Un parseur par mot-clé
aurait raté la quatrième **sans lever d'erreur** — c'est la forme de panne que ce dépôt paie le
plus cher, et ici elle fait manger de la viande à une pescétarienne.

## Décision

**Deux colonnes sur `recipe_ingredient`** :

```sql
for_person_id     INTEGER REFERENCES person(id) ON DELETE SET NULL
replaces_position INTEGER
```

`for_person_id` dit **pour qui** cette ligne est achetée et cuisinée. `replaces_position` dit
**quelle ligne du plat commun elle remplace, pour cette personne** — sans elle, la part
s'ajouterait au plat au lieu de s'y substituer.

```
pos 1  filets de poulet fermier 480 g   for_person: NULL
pos 2  crevettes 150 g                  for_person: Clémence, replaces_position: 1
```

**`ON DELETE SET NULL`, jamais CASCADE** : retirer une personne du référentiel ne doit pas
effacer la ligne d'ingrédient — elle redeviendrait du plat commun en silence.

**Chaque convive lit SA tablée.** `check_ingredients` reçoit `person_ids` et construit, pour
chacun, la liste des lignes qui le concernent (`lines_for_person`) : le plat commun moins ce que
sa part remplace, plus sa part. Une part déclarée pour **quelqu'un d'autre** ne le couvre pas.

**Le texte cesse de faire autorité.** `declared_diets` lit `for_person_id` : une fiche non migrée
remonte désormais comme **non réparée**, au lieu de passer pour couverte par une parenthèse.

**Un gate à l'écriture.** `write_recipe_ingredients` refuse en 422 une ligne dont le texte
annonce la part d'un convive **connu du référentiel** sans porter `for_person_id`. Le garde est
posé dans l'écriture partagée, pas chez ses appelants : les trois chemins (POST/PUT recette,
ingest, commit d'import) passent par elle.

**Une colonne non chargée lève.** `declared_parts` refuse un dict où la clé `for_person_id` est
**absente** — distinct d'un `None`, qui dit « lu, aucune part ». Sans ce garde, une requête qui
oublie la colonne rend « aucune part » et la viande recompte contre Clémence, sans erreur. C'est
exactement la panne qui s'est produite pendant l'implémentation, sur
`/api/recipes/{slug}/compatibility`.

## Alternatives rejetées

- **Parser `(part de X)`** : trois orthographes existaient déjà, la quatrième passerait muette.
- **Une table `recipe_part` séparée** : deux sources à départager pour une donnée qui appartient
  à la ligne d'ingrédient.
- **Réécrire les titres des fiches** (`…-poulet-fermier`) : décision de Julien au grill — le titre
  nomme la version majoritaire, pas l'exception.
- **Utiliser `substitution_discovery`** : ses colonnes (`outcome`, `who_preferred`, `verbatim`,
  `served_on`) en font un registre de **retour de table**, pas de planification.

## Conséquences

- **7 lignes migrées** le 2026-09-25 (`scripts/migrate_parts_159.sql`, sous transaction, avec
  contrôle préalable que chaque cible existe) : 6 substitutions pour Clémence, plus une part de
  concombre pour Léa **sans `replaces_position`** — elle s'ajoute, elle ne remplace rien.
  La parenthèse est retirée de `name`, `raw` et `name_normalized` : la donnée porte le convive,
  le nom porte l'aliment, et la liste de courses sait enfin pour qui elle achète.
- **Deux conflits subsistent et sont justes** : `mafe-poulet` et `chili-con-carne-facile`
  déclarent un **bouillon** de volaille ou de bœuf que la part ne remplace pas. La donnée les
  fait apparaître ; ils étaient masqués par la parenthèse.
- `/recipes/{slug}/compatibility` rend `declared_parts` et `parts_undeclared`.
- Supersède partiellement l'ADR 0025 : `part_for()` reste pour les appels sans `person_ids`, mais
  n'est plus la source d'autorité.
