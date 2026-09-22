---
numero: 0031
titre: Un service partagé par un seul consommateur redevient un module
statut: accepté
date: 2026-09-22
concerne:
  - backend/app.py
  - backend/db.py
  - pyproject.toml
  - deploy/cooking-manager.service
  - deploy/cooking-manager.nginx.conf
supersede: ADR 0005 (dépôt cooking-manager-2-handoff-20260901)
---

# 0031 — Un service partagé par un seul consommateur redevient un module

## Contexte

recipe-manager a été extrait de CM2 le 2026-08-08 pour une raison déclarée : servir de modèle
canonique de recettes à **deux** consommateurs, CM2 en colocataire de base et Waaker par API.
Le registre et le README du dépôt le disent tous les deux. Un handoff du 2026-09-11
(`docs/rapports/_HANDOFF-next-llm_recipe-manager-etage-de-trop.md`) posait la question pivot sans
pouvoir la trancher : Waaker consomme-t-il réellement ce modèle ?

Mesures du 2026-09-22.

**Waaker ne consomme pas le modèle, il consomme un parseur.** `waaker/src/lib/parsers.ts:78`
appelle `POST /parse-html`, et c'est le seul point d'appel — une route sur les 24. Waaker porte ses
propres tables de recettes en SQLite (`recipes`, `meals`, `recipe_votes`, `meal_cooks`,
`shopping_items`, dans `src/lib/db.ts`). Pour les données, il s'adresse directement à CM2 :
`scripts/import-cooking-manager.ts:25` pointe sur le port 8795.

**Le coût de dépendance invoqué n'existe pas.** recipe-manager déclare huit dépendances, CM2 en
déclare huit, **six sont communes**. L'absorption ajoute exactement `pillow` et `python-multipart` ;
`ollama` y est optionnel, la génération d'image passe par un appel HTTP. Le venv de CM2 pèse 230 Mo,
celui de recipe-manager 110 Mo ; en mémoire, 55 Mo de RSS contre 82 Mo.

**Le coût de latence invoqué se mesure à 25 ms.** Un aller-retour HTTP complet vers `/parse-html`
sur une page de 165 Ko prend 24 à 27 ms. Le parse *réussi* n'a pas pu être chronométré : Marmiton
et CuisineAZ ont tous deux refusé le téléchargement depuis le VPS. Le chemin `pillow` de l'import
de livre photographié reste **non mesuré**.

**Les deux services partagent déjà une seule base**, `cooking_manager`, 38 tables. La séparation
n'isole donc aucune donnée : elle ne sépare qu'un fichier de schéma et un process.

**Dix-neuf des 24 routes ont déjà un jumeau dans CM2.** Sont propres à recipe-manager : `/parse`,
`/parse-html`, `/recipes/import/page`, `/recipes/{slug}/generate-image`, et `/recipes/import/url`
que CM2 relaie.

Deux mesures ne disent rien et sont écartées comme telles. `/api/recipes-shared/` compte 2 requêtes
sur 127 046 lignes de log entre le 05/09 et le 22/09 — mais Waaker tourne sur le même VPS et appelle
`127.0.0.1:8796` sans passer par nginx, donc ce chiffre ne mesure pas Waaker. Le journal systemd de
recipe-manager ne remonte qu'au 20/09 : ses 11 appels, tous `generate-image` et tous émis par CM2,
couvrent deux jours, pas trente.

## Décision

recipe-manager est absorbé **en totalité** dans CM2, parseur compris. Un seul process, port 8795.

1. Les cinq tables (`recipe`, `recipe_ingredient`, `recipe_step`, `recipe_execution`,
   `import_draft`) passent sous `backend/db.py`. CM2 cesse d'être colocataire et devient
   propriétaire.
2. Les routes propres deviennent `/api/recipes/parse`, `/api/recipes/parse-html`,
   `/api/recipes/import/page`, `/api/recipes/{slug}/generate-image`. Les façades HTTP de
   `backend/app.py:3109-3180` disparaissent avec `RECIPE_MANAGER_URL`.
3. `POST /api/recipes/import/page` devient asynchrone : il rend `202` et un identifiant de tâche,
   parce que la durée du décodage d'image n'est pas mesurée. `parse`, `parse-html` et
   `generate-image` restent synchrones.
4. Waaker change une ligne, `src/lib/parsers.ts:1`, le même jour. `recipe-manager.service` est
   arrêté et désactivé dans la foulée ; `deploy/cooking-manager.service` perd son `Requires=`.
5. Le dépôt `theflysurfer/recipe-manager` est archivé. Le registre passe en `archived` et la
   relation « fournit à Waaker (modèle de recettes partagé) » est retirée : elle n'a jamais décrit
   ce que le code fait.
6. Les 118 `.md` du vault sont supprimés, y compris forcé côté cloud Dropbox. `recipe_manager/
   vault.py` disparaît avec le reste. `backend/ingest.py` ne lisait déjà plus le vault ; plus rien
   ne l'écrira.

## Conséquences

- L'app cuisine, toujours allumée et visée pour l'iPad mini 2, porte désormais le parsing HTML et
  la génération d'image. Le risque est chiffré à 25 ms pour le parsing et reporté en tâche de fond
  pour l'import de livre, seul chemin dont la durée est inconnue.
- `ALTER TABLE recipe_ingredient` cesse de traverser une frontière de dépôt. C'est ce qui rend
  l'ADR 0032 possible sans table de liaison ni ordre de déploiement contraint.
- Waaker dépend de CM2 pour son parseur comme il en dépend déjà pour ses menus. Le couplage
  n'augmente pas : il devient visible et unique.
- Deux paquets entrent dans le runtime de CM2. Aucun SDK, aucun OCR, aucun torch.
- L'extraction du 2026-08-08 est défaite. Son motif était vrai au moment où il a été écrit — un
  second consommateur était prévu — et ne l'est jamais devenu.
- Le dual-writer signalé par le handoff du 11/09 meurt avec le vault : plus aucune recette n'existe
  à deux endroits, donc plus aucun écrasement silencieux au prochain ingest.

## Alternatives écartées

- **Absorber les tables et garder un service de parsing** : cohérent avec l'usage réel de Waaker,
  mais maintient un déployable, un dépôt et une adresse pour trois routes qui coûtent 25 ms. Le
  couplage qu'il évite est celui que Waaker accepte déjà par ailleurs.
- **Statu quo** : laisse `recipe_ingredient` chez un voisin. Le rattachement d'aliment exigerait
  soit un `ALTER TABLE` dans un deuxième dépôt avec un ordre de déploiement contraint, soit une
  table de liaison `ingredient_food` — une jointure de plus, et des lignes orphelines à nettoyer
  quand recipe-manager supprime un ingrédient.
- **Waaker embarque son propre parseur** : coupe toute dépendance, mais grave le doublon
  d'extraction JSON-LD déjà signalé par `deep-research#51` et `recipe-manager#4`.
- **Garder 8796 en alias le temps que Waaker migre** : une ligne à changer ne justifie pas deux
  adresses vivantes, dont une que personne ne se souviendra de couper.
- **Supprimer le dépôt plutôt que l'archiver** : emporterait `docs/CORPUS_WEB.md`,
  `scripts/measure_parse_url.py` et les tests de parsing par site, qui portent les leçons sur les
  sites qui bloquent.
