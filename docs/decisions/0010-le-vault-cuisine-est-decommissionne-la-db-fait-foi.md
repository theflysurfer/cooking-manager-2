# 0010 — Le vault cuisine est décommissionné, la DB fait foi

- **Statut** : accepté
- **Date** : 2026-09-07
- **Porte** : `docs/conception/SPEC_referentiel-aliment-produit.md` (sous-projet 1)
- **Issues** : #69, #84

## Contexte

Quatre fichiers du vault faisaient autorité — `Recettes/*.md`, `Menus/*.md`,
`Convives.md`, `Garde-manger.md` — et deux écrivains les touchaient sans se voir :
l'app (par ingestion) et le Cooking Coach de claude.ai (par écriture directe).

Les deux stocks divergeaient sans alerte, et le fichier plat ne pouvait porter ni
historique, ni source, ni date par article. Trois défauts mesurés le 2026-09-07
en découlent : la fraîcheur jugée sur `MAX(updated_at)` (#84), l'absence
d'identité d'aliment (#69), et 24 articles sans date d'entrée.

## Décision

1. **La DB est la seule source de vérité.** Les fichiers du vault cuisine sont
   **décommissionnés**, pas mis en lecture seule : un fichier encore écrit reste
   un écrivain.
2. **Le Coach Nutrition de claude.ai écrit par le MCP** (`cooking-mcp`, 3868),
   comme tout le monde.
3. **L'agent écrit via MCP uniquement ; l'app reste en lecture.** Aucun éditeur
   de recette ou de menu n'est construit dans le front.
4. **Le stock ne bouge que sur déclaration humaine.** Marquer un repas « mangé »
   propose ses ingrédients ; il ne retranche rien tout seul.
5. **Le référentiel aliment du Coach Nutrition** (`aliments-vérifiés/`, 249
   fiches) **entre dans le périmètre** : `generiques/` devient l'aliment,
   `marques/` devient le produit.

La bascule se fait en cinq sous-projets, chacun livrable seul, et chacun finit
par le **retrait du code de lecture** correspondant.

## Conséquences

- Un flux disparaît entièrement : `rclone copy` → mount → `POST /api/ingest`,
  avec son délai de propagation de 30 s et ses menus orphelins.
- `nutrition.py` lit la DB. Ses trois sources hiérarchisées deviennent deux
  tables et une règle de préférence.
- Chaque migration doit **prouver son équivalence** avant que le vault se taise :
  un rapport article par article, dont un écart non expliqué bloque la suite.
- Julien perd l'édition libre dans Obsidian. C'est accepté : dans les faits,
  l'écrivain des fiches et des menus est l'agent depuis des semaines.

## Écarté

- **Garder le fichier comme lieu d'écriture partagé.** Simple et robuste, mais
  perd ce qu'un fichier plat ne sait pas porter — et laisse deux écrivains
  s'écraser en silence.
- **Réconcilier les deux mondes** par une passe de comparaison permanente. Le
  plus honnête, le plus coûteux : il faut lire le rapport chaque semaine, et
  personne ne le fera.
- **Un décrément automatique du stock à la cuisson.** Une recette imprécise ou
  un plat modifié en cuisine ferait dériver l'inventaire sans que rien ne le
  signale — le motif exact que ce dépôt corrige partout ailleurs.
- **Décommissionner `Garde-manger.md` seul.** Le stock aurait migré pendant que
  les recettes et les menus continuaient d'arriver par un autre chemin.
