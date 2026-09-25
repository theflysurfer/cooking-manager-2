---
numero: 0036
titre: Le garde-manger se quantifie à l'entrée et se confirme avant le panier
statut: accepté
date: 2026-09-25
concerne:
  - cooking_manager/pantry.py
  - backend/app.py
  - backend/db.py
  - backend/cooking_mcp.py
issue: 161
---

# 0036 — Le garde-manger se quantifie à l'entrée et se confirme avant le panier

## Contexte

`pantry_item` est un **journal d'entrées**, pas un inventaire : rien ne le décrémente. `ok` dit
« acheté un jour », jamais « il y en a ». Deux mesures du 2026-09-21 :

- toutes les lignes entrées ce jour-là portaient `qty_value = NULL`, alors que les colonnes
  `qty_value` et `unit` existent depuis l'origine (`backend/db.py:226-227`) ;
- `is_stale: false` le même jour — le stock était **frais et faux**, 4 articles présents
  sortaient `absent` de la liste de courses.

Un âge récent dit que quelqu'un a écrit, jamais que ce qui est écrit est vrai. Et une ligne sans
quantité ne se compare à aucun besoin : `check_need` rend `inconnu`, ce que la liste lit comme un
manque ou comme une couverture selon le chemin.

Trois des cinq chemins d'écriture (`PATCH /api/pantry`, `POST /api/pantry/items`,
`POST /api/pantry/leftover`) n'écrivaient d'ailleurs **ni `qty_value` ni `unit`**, même quand
`qty_text` en portait : la donnée était perdue à l'entrée, sans erreur.

## Décision

**1. La quantité devient obligatoire à l'entrée.** Un statut `ok` ou `low` sans quantité
mesurable est refusé en 422 avec son motif, sur les **cinq** chemins d'écriture — `PATCH
/api/pantry`, `POST /api/pantry/items`, `PUT /api/pantry/items/{id}`, `POST /api/pantry/bulk` et
`POST /api/pantry/leftover`. Un garde posé sur quatre appelants sur cinq n'en est pas un. Un `out` n'exige
rien : il n'y a rien à mesurer. La règle vit dans `entry_quantity()`, dans le domaine, pas dans
les routes.

**Toujours aucun décrément.** Ce qui *reste* demeure inconnu : c'est un journal quantifié, pas un
inventaire. Le décrément au `POST /served` a été écarté — un seul `served` oublié ferait dériver
le stock sans rien lever, et une dérive silencieuse est pire qu'une absence déclarée.

**2. Un gate avant que le panier parte.** `POST /api/menus/{slug}/pantry-confirm` enregistre le
garde-manger confronté pour ce menu ; `POST /api/shopping/validate-cart` exige désormais son
`menu_slug` et rend `ok: false` tant que la confrontation n'a pas eu lieu. Le `menu_slug` est
**requis**, pas optionnel : un gate qu'on saute en omettant un champ n'est pas un gate.

Une confirmation est datée et périme à 7 jours. Une confirmation sans date ne se juge pas et
bloque — elle ne dit pas ce qu'elle vaut.

**3. Une échappatoire qui s'écrit.** `{"blind": true, "reason": "…"}` laisse passer, et la liste
de courses porte alors `confirmé À L'AVEUGLE le <date> — <motif>`. Un `blind` **sans motif n'est
pas une confirmation** : c'est le seul cas où l'échappatoire elle-même est refusée.

## Alternatives rejetées

- **Décrémenter au `served`** : rejeté ci-dessus.
- **`menu_slug` optionnel sur `validate-cart`** : aurait gardé la compatibilité des appelants,
  au prix d'un gate contournable en silence. La rupture est assumée et visible (422 de FastAPI).
- **Bloquer sans échappatoire** : une règle sans sortie se contourne autrement. La commande
  partirait directement sur auchan.fr, et là il ne resterait **aucune trace**. L'aveugle tracé
  vaut mieux que le contournement muet.
- **Refuser tout le batch `POST /api/pantry/bulk`** : l'inventaire vocal accepte déjà des lignes
  partielles. Les lignes sans quantité sortent en `rejected` avec leur motif, et le compte
  `rejected` figure dans la réponse — un refus qui ne se compte pas ne se voit pas.

## Conséquences

- **Une ligne historique reste modifiable.** Le `PUT` ne refuse que si l'appel déclare une
  quantité, ou s'il fait entrer la ligne en stock (`out` → `ok`/`low`) : corriger le nom ou la
  section d'un article legacy « 1 paquet » ne se heurte pas au gate.
- **`qty_text`, `qty_value` et `unit` s'écrivent ensemble**, jamais l'un sans les autres. Un texte
  « 500 g » conservé à côté d'un `qty_value` remis à NULL ferait lire une quantité que la colonne
  chiffrée dément.
- Les lignes déjà en base restent à `qty_value = NULL`. Elles ne se réparent pas seules : le gate
  ne mesure que ce qui entre **après**. La première `pantry-confirm` d'un menu est ce qui les
  requalifie une à une.
- `GET /api/menus/{slug}/shopping-list` porte `pantry.confirmation` — `ok`, `blind`, `note`,
  `confirmed_at`, `lines_count`. Comme pour `slots_uncomposed`, **ce champ se lit avant `lines`** :
  une liste calculée sur un stock non confirmé n'est pas fausse, elle est non instruite.
- Ferme #94 par la négative (on ne décrémente pas) et répond à #120 (une confirmation a un foyer).

Refs #154 (état 2), #161, #94, #120.
