# 0017 — L'ingestion du vault ne touche plus au garde-manger

- **Statut** : accepté
- **Date** : 2026-09-08
- **Porte** : `backend/ingest.py`, `backend/cooking_mcp.py`
- **Issues** : #91, #69, #84
- **Supersède** : la garantie « `source != 'vault'` survit à la ré-ingestion »
  annoncée avec #69 — elle n'a jamais été exécutée par quoi que ce soit
- **Voir aussi** : ADR 0010 (le vault cuisine est décommissionné), ADR 0015

## Contexte

`_ingest_pantry` lisait `Garde-manger.md` et l'écrivait dans `pantry_item` par
`ON CONFLICT (name_normalized, section) DO UPDATE SET … source = 'vault'`, sans
condition sur la source de la ligne trouvée. La table portant un `UNIQUE
(name_normalized, section)`, un article ne peut exister qu'une fois : le vault ne
créait pas un doublon à côté d'une ligne de drive, il la **convertissait** — nom,
quantité, statut, date d'entrée et source remplacés par ceux du fichier.

Mesuré en production le 2026-09-08 : **14 lignes sur 36** d'un report de drive du
matin repassées en `source = 'vault'` avec leur ancien `status` et leur ancien
`entered_at`, et 5 doublons supprimés à la main revenus avec de nouveaux ids. La
liste de courses a rendu `champignons de Paris — absent, marqué épuisé` pour des
champignons achetés la veille : un rachat.

Deux traits rendent le défaut coûteux :

1. **Il se déclenche sur des gestes qui n'ont rien à voir avec le stock.**
   `POST /api/ingest` est appelé pour republier un menu, et aussi par
   `commit_import_draft` — importer une fiche de livre défaisait le garde-manger.
2. **Il est silencieux.** Aucune erreur, aucun avertissement ; le stock change et
   se relit comme un stock.

Le fichier, lui, n'était plus écrit depuis le 2026-09-01, l'ADR 0010 ayant
décommissionné le vault cuisine au profit du MCP.

## Décision

**L'ingestion du vault cesse de lire `Garde-manger.md`.** `_ingest_pantry` est
retirée, avec la clé `pantry_items` de la réponse de `/api/ingest` : une clé qui
compte ce qui n'est plus fait est un chiffre rassurant sans mesure derrière.

Le stock ne se modifie plus que par déclaration explicite — `PATCH /api/pantry`,
le report d'un drive, un ticket de caisse — conformément à l'ADR 0010 §4, dont
chaque sous-projet doit finir par le retrait du code de lecture correspondant.

L'outil MCP `pantry_ingest` devient **`vault_ingest`** : il n'a jamais ingéré le
garde-manger seul, et il ne l'atteint plus du tout. Un nom qui promet ce que le
code ne fait plus est la même panne, déplacée dans le vocabulaire.

Les 238 lignes déjà en base en `source = 'vault'` **restent**. Elles ne sont plus
réimposées à chaque ingestion, elles vieillissent et se corrigent article par
article. Les supprimer effacerait un fond de placard réel — 153 des 183 lignes
`ok` sont des stables (épices, condiments, surgelés, épicerie sèche).

## Conséquences

- Un fichier réécrit dans le vault n'atteint plus la base par aucun chemin. C'est
  voulu : l'écrivain déclaré est le MCP. Il n'existe **aucune** route de réimport,
  et il ne s'en écrira pas une tant que personne n'en a besoin.
- La garantie de #69 n'a plus à être défendue : il n'y a plus d'écrivain à
  contredire. Le garde-fou est structurel, pas conditionnel.
- `tests/test_ingest_isolation.py` échoue si `pantry_item`, `garde-manger` ou
  `parse_pantry` réapparaît dans `backend/ingest.py`, et porte le contrôle
  inverse qui prouve que la lecture du fichier de test n'est pas vide.
- `cooking_manager/pantry.py` reste : `parse_pantry` sert encore aux tests et au
  parsing d'un texte de garde-manger hors ingestion.
- Les 12 périssables sans `entered_at` portent leur date dans le `qty_text`
  (« constaté 2026-08-06 ») — la colonne reste vide et `age_days` ne les voit
  pas (#84). Cet ADR ne les corrige pas.

## Écarté

- **Rendre l'upsert respectueux** (`WHERE pantry_item.source = 'vault'`). Une
  ligne de SQL, et le rachat n'aurait plus eu lieu. Mais la lecture d'un fichier
  décommissionné restait vivante, une ligne supprimée à la main revenait à
  l'ingestion suivante, et la règle redevenait une promesse tenue par une clause
  qu'un futur refactor peut laisser tomber sans erreur.
- **Une route explicite `POST /api/pantry/import-vault`.** Le geste devenait
  volontaire et traçable, mais c'est du code sans appelant : le fichier n'est
  plus écrit, et le MCP couvre déjà l'écriture.
- **Supprimer les 238 lignes `vault`.** Rapide et faux : elles sont pour 153
  d'entre elles le fond de placard, et rien d'autre ne le porte.
