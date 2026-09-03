# 0002 — La hiérarchie des modes de cuisson vit dans le vocabulaire, pas dans le code

- **Date** : 2026-09-03
- **Statut** : accepté
- **Contexte d'origine** : `docs/rapports/2026.09.03_13.16_3ad96ea_SESSION_dominance-cuissons-recompte-tablee.md`, SC-68, issue #53
- **Complète** : [0001](0001-moteur-de-substitutions-porte-de-la-v1.md)

## Contexte

Le moteur de substitutions score une règle par sa priorité de base plus un bonus par
dimension de contexte appariée : `CUISINE_BONUS = 20`, `COOKING_METHOD_BONUS = 40`.

Le corpus web a montré que ce barème traite à égalité deux choses qui ne le sont pas.
« Cocotte de poulet mijoté de ma grand-mère » rendait **dorade** :

| Règle | priorité | bonus cuisine | bonus cuisson | total |
|---|---|---|---|---|
| dorade *(grilled, oven, **pan-fried**)* | 90 | +20 | **+40** | **150** |
| lotte *(**stew**, slow-cooked)* | 95 | +0 | +40 | 135 |

`pan-fried` venait de « **faites revenir** les morceaux de poulet ». Cette étape de saisie
ouvre presque tout mijoté : le rissolage y est une **préparation**, pas la cuisson qui
définit le plat. Une dorade grillée gagnait donc dans une cocotte.

C'est la même erreur de forme que « l'étape de garniture pilote le plat », déjà corrigée
côté accommodation par `is_accommodation_step()` : une phrase qui décrit autre chose que
le plat ne doit pas décider du plat.

## Décision

Un mode de cuisson **déclare ce qu'il absorbe**, dans
`data/ontology/cooking-vocabulary.yaml` :

```yaml
- key: stew
  dominates: ["pan-fried", "pan-seared", "stir-fry"]
```

`drop_dominated()` retire du contexte les modes absorbés **avant tout scoring**, dans
`detect_context()`. Le barème n'est pas touché : ce qui change est la composition du
contexte, pas le poids des dimensions.

Trois conséquences volontaires :

1. **La relation est orientée et interne à une facette.** Le chargement d'ontology-manager
   refuse une clé inconnue ou auto-citée — sinon la règle ne s'appliquerait jamais, en
   silence.
2. **La table ne porte que ce qui a été observé.** `oven` dominant `pan-seared` (saisir
   puis enfourner) est plausible et n'a pas été mesuré : l'y inscrire serait exactement le
   défaut reproché à `separate_dish`, une intuition qui pèse comme une pratique.
3. **`drop_dominated()` est neutre hors mijoté.** Sans mode dominant détecté, rien n'est
   retiré : une vraie poêlée reste `pan-fried`.

## Pourquoi le vocabulaire et pas le code

Une table de dominance écrite en Python serait invisible à `julien-audit-cooking-vault`,
qui audite le vocabulaire, et divergerait du YAML sans produire d'erreur. Le vocabulaire
est déjà le foyer déclaré des cuissons, des cuisines, des textures et des accommodations
(CLAUDE.md, § Gotchas) ; une hiérarchie entre cuissons est une propriété des cuissons.

## Alternatives rejetées

- **Pondérer selon la position de l'étape** — une méthode détectée dans la première étape
  reçoit un bonus réduit. Plus fin en théorie, mais dépend de **l'ordre de rédaction** :
  fragile sur une fiche mal écrite, et surtout sur une fiche importée du web, dont on ne
  maîtrise pas la structure. Le cas d'usage qui monte (SC-33) est précisément celui-là.
- **Bonus dégressif quand plusieurs modes matchent** — le premier apparié garde 40, les
  suivants tombent. Purement mécanique, donc arbitraire : le « premier » dépend de l'ordre
  de déclaration du vocabulaire, pas du plat.
- **Relever la priorité de la lotte** — corrige un cas, ne dit rien du défaut, et déplace
  le problème sur la règle suivante.

## Vérification

En production le 2026-09-03, sur `mafe-poulet` qui contient « faire revenir les oignons »
**et** « saisir les crevettes » :

```bash
curl -s https://cooking.srv759970.hstgr.cloud/api/recipes/mafe-poulet/compatibility
# context.cooking_methods == ["stew"]
```

Deux tests ancrent la règle : le mijoté absorbe le rissolage, et une vraie poêlée reste
poêlée.

## Conséquence pour ontology-manager

Le générateur avait un **jeu de champs fixe** : ni `dominates` (nouveau) ni `observed_in`
(déclaré depuis la v0.2.0) n'atteignaient l'artefact JSON. Les deux sont désormais
propagés. Le second cas est le plus instructif : un tri par force de preuve aurait compté
**zéro observation partout** et aurait paru fonctionner. Ajouter un champ à ce vocabulaire
exige donc de toucher les deux dépôts, plus un test qui prouve qu'il survit à la
génération.
