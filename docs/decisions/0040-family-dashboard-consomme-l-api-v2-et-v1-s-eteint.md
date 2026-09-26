---
numero: 0040
titre: family-dashboard consomme l'API v2, et cooking-manager v1 s'éteint
statut: accepté
date: 2026-09-26
concerne:
  - family-manager (theflysurfer/family-manager)
  - /opt/cooking-manager (v1, srv759970)
  - repo-registry (data/deployments.json)
---

# 0040 — family-dashboard consomme l'API v2, et cooking-manager v1 s'éteint

## Contexte

Deux déploiements de cuisine coexistent sur srv759970 depuis le 2026-08-04, sans périmètre
tranché : `/opt/cooking-manager` (v1, `theflysurfer/cooking-manager`) et `/opt/cooking-manager-2`
(CM2). L'issue #20 portait la question depuis, et family-manager#41 en avait déjà montré le
symptôme : le fix d'août pour afficher le menu était passé par v1, pas par l'API de CM2.

Mesures du 2026-09-26 sur srv759970.

**v1 ne produit plus rien depuis le 2026-09-01.** Son cron `27 6 * * *` construit
`/home/automation/family-dashboard/data/cuisine.json`. Le fichier date du 2026-09-01 06:27, et
`logs/cuisine-build.log` n'a plus reçu une ligne depuis cette date — 25 jours. Le cron ne
s'exécute plus, ou échoue avant d'écrire ; rien ne l'a signalé.

**L'artefact figé annonce « 0 repas ».** Sa dernière ligne de log dit `256 items (11 bas, 56 en
rupture) · 56 recettes · 0 repas`. v1 dérive le menu des lignes `#food` de `Planning-famille.md`,
c'est-à-dire d'un vault **déconnecté depuis les ADR 0010/0022**. Ce zéro ne dit pas « pas de menu
cette semaine » : il dit « je lis une source morte ». Pendant ce temps CM2 porte 149 recettes.

**Le garde-fou de fraîcheur existe et ne sait pas échouer ici.** `family_dashboard/manifest.py`
donne deux plafonds au **même fichier** : `pantry` à 14 jours, `kitchen` à 30. Sur un artefact de
25 jours, le garde-manger ressort `stale` et la Cuisine ressort **`fresh`**. Un même fichier mort
rend donc deux verdicts opposés selon la slide.

**Le contrat de lecture est étroit.** `family_dashboard/cuisine.py` attend un schéma `cuisine/1`
avec `pantry`, `recipes`, `menu`, `counts`. Il refuse déjà un schéma inconnu et signale un fichier
absent — mais rien ne lui fait lire l'âge de ce qu'il sert.

## Décision

**family-dashboard consomme l'API de CM2** (`localhost:8795`), et v1 s'éteint : son cron de 6h27,
`/opt/cooking-manager` et son `cuisine.json`. Une seule source de vérité, celle qui porte les
recettes et les menus réellement composés.

1. La forme exacte se tranche à l'implémentation, dans family-manager#42 : soit CM2 produit le
   même artefact `cuisine/1` depuis sa base et le cron change seulement de producteur, soit le
   dashboard appelle l'API en direct et compose `cuisine/1` lui-même. La première a le diff
   minimal, la seconde supprime la classe de panne.
2. Dans les deux cas, **l'artefact porte un `generated_at` que le lecteur lit**. « Absent » n'est
   pas « périmé », et « périmé » n'est pas « vide ».
3. Dans les deux cas, **« 0 repas » cesse de pouvoir s'afficher comme une mesure** : zéro parce
   que la semaine n'est pas composée et zéro parce que la source est injoignable sont deux états
   distincts, et seul le premier est une information.
4. Le plafond de fraîcheur de `kitchen` descend à l'ordre de la semaine : un menu ne survit pas
   30 jours par construction.
5. L'extinction de v1 ne précède pas la migration. Couper la production avant que le consommateur
   soit migré rendrait `missing` au lieu de figé — plus honnête, toujours vide.
6. Une fois éteint, le retrait est déclaré dans `repo-registry` (`data/deployments.json`), et #20
   se referme là-dessus.

## Conséquences

- CM2 devient la source unique du domaine cuisine pour la maison, comme il l'est déjà pour ses
  propres consommateurs. La non-décision du 2026-08-04 cesse d'avoir un coût.
- family-manager gagne une dépendance explicite à CM2 — qu'il a déjà par ailleurs, puisque
  `scripts/import-cooking-manager.ts` pointe sur le port 8795.
- Le vault perd son dernier consommateur indirect. Plus rien ne dérive un menu d'un `.md`.
- Un garde-fou de fraîcheur incohérent entre deux slides du même fichier est corrigé. C'est la
  leçon la plus réutilisable : **un plafond par module sur une source partagée se contredit en
  silence**.

## Alternatives écartées

- **Réparer le cron v1** : remettrait le dashboard à jour en quelques minutes, mais il lirait
  toujours le vault déconnecté et continuerait d'annoncer « 0 repas ». Répare l'affichage, pas la
  source.
- **Éteindre v1 tout de suite, migrer ensuite** : un dashboard franchement vide vaut mieux qu'un
  dashboard faux, mais prive la maison de l'écran pendant l'intervalle sans nécessité — la
  migration n'attend pas l'extinction pour commencer.
- **Laisser coexister avec un périmètre documenté** : c'est exactement ce que #20 proposait en
  août comme option, et la coexistence a produit 25 jours d'affichage faux sans que personne ne
  le voie. Documenter une frontière ne la fait pas tenir.
