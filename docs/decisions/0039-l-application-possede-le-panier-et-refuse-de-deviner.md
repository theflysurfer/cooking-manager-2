# 0039 — L'application possède le panier, et refuse de deviner

- **Statut** : accepté
- **Date** : 2026-09-25
- **Concerne** : `cart_item`, `backend/auchan.py`, `cooking_manager/election.py`,
  `POST /api/cart/items`, `POST /api/cart/push`, `GET /api/cart`
- **Résout** : #156 · **Cadre** : #154 (état 6) · **Voisin** : #113

## Contexte

`validate-cart` recevait `body.items` du dehors et ne comparait rien au menu :
l'application ne voyait pas le panier, elle le prenait sur parole. Le 2026-09-21, le
contenu réel d'une commande de 46 lignes n'était reconstituable que par le navigateur, et
deux retours de Julien — « il y avait 6 paquets de parmesan », « il manque des carottes ? »
— n'ont pu être instruits ni l'un ni l'autre.

Le transport manquait aussi : le MCP Auchan exige un jeton Google même depuis la boucle
locale (mesuré le 2026-09-25, `401 invalid_token`). Une application n'a pas de doigts pour
cliquer sur un écran de consentement.

## Décision

**Le panier est une table de l'application.** `cart_item` porte chaque ligne AVANT tout
départ vers le drive, avec son `origin` (`menu`, `manual`, `recurrent`, `substitution`) et
son `reason`. Un ajout à la main est une ligne comme une autre : il se déclare, il ne se
subit pas.

**L'élection est bornée, et son refus est une réponse.** `elect()` (domaine pur) rend
l'un de trois verdicts :

| Verdict | Quand | Trace |
|---|---|---|
| `elected` | le produit nommé est disponible et non banni, ou — si la liste ne nomme aucun produit — un produit du même aliment, gamme non bannie, contenant équivalent | `origin: menu` |
| `substitution` | la liste nommait un produit précis, indisponible, et un autre tient dans les mêmes bornes | `origin: substitution` + le motif |
| `ask` | hors de ces bornes | `status: asked`, la **question** dans `reason` |

Les trois bornes sont celles du menu : **même aliment, gamme autorisée, contenant
équivalent**. Un contenant voulu **inconnu** ne vaut pas « contenant quelconque » — il rend
`ask`. Chaque produit écarté part avec son motif (`rupture`, `gamme refusée (X)`, `autre
aliment`, `contenant différent`) : une liste de candidats vide ne se lit jamais comme une
absence de produit.

**Chaque ajout se relit.** `POST /api/cart/push` rejoue les lignes **une par une** (jamais
en parallèle) et recompte la ligne dans le panier après l'ajout : un `ok` du drive ne
garantit aucune quantité, dans les deux sens. Un ajout qui ne change rien devient
`status: failed` avec son motif, pas un succès.

**Une session anonyme n'est pas un panier.** `push` lit `session_status()` d'abord et rend
**409** si `authenticated` est faux : un panier anonyme est parfaitement crédible et
n'appartient à personne.

**Le transport est une façade REST loopback** de `mcp-vps-auchan` (mcp-vps ADR 0009),
`127.0.0.1:3853`. `cooking_manager/` reste sans I/O réseau : le client vit dans
`backend/auchan.py`, et une panne de transport **lève** (`DriveUnreachable`) au lieu de
rendre une liste vide.

## Conséquences

- `GET /api/cart` rend `counts.asked` **avant** `lines` : des lignes élues sans regarder
  les lignes en attente donnent un panier qui se croit complet.
- Le test d'identité alimentaire hérite de `matching._names_concord`, qui exige que le nom
  court **ouvre** le nom long. « poulet » n'ouvre pas « filets de poulet jaune » : ces
  produits partent en `autre aliment` et la ligne devient `asked`. Conservateur et visible
  — jamais une substitution fausse, mais plus de questions que nécessaire (#164).
- `validate-cart` garde son rôle de contrôle de sortie ; il lit désormais un panier dont
  l'application connaît chaque ligne et chaque origine.
