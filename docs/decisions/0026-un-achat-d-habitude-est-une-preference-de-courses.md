---
numero: 0026
titre: Un achat d'habitude est une préférence de courses, pas une table
statut: accepté
date: 2026-09-21
concerne:
  - cooking_manager/bans.py
  - backend/app.py
  - backend/db.py
---

# 0026 — Un achat d'habitude est une préférence de courses, pas une table

## Contexte

Un pan entier des courses ne dérive d'aucun repas : desserts, fromages, laitages de fin de
repas, céréales du matin, à-côtés. Aucune fiche recette ne les portera jamais, parce
qu'aucun repas ne les nomme. Ils s'achètent par habitude, et cette habitude ne vivait que
dans la tête de Julien — 14 lignes (~45 €) sont apparues à la main dans le panier du
2026-09-20 sans qu'aucun calcul ne les ait réclamées (#89).

La forme proposée dans #89 était une notion de **produit récurrent** : EAN, famille,
fréquence observée, dernière commande. Elle appelait naturellement une table dédiée.

Deux mesures ont fait tomber la moitié de cette forme :

- `grocery_order_detail` **ne rend aucun EAN** (mcp-vps#182). Ses lignes portent `name`,
  `category`, `price`, `quantity`. La clé ne peut donc pas être l'EAN.
- Sa `category` est **fausse**, pas imprécise : toute la section fruits et légumes de la
  commande du 11/09 est classée « Hygiène, beauté ». La famille n'est pas dérivable.

Il restait : un libellé, une fréquence, une date. Trois champs texte.

## Décision

Un produit récurrent est une ligne `shopping_preference` de `pref_type = 'recurrent'` —
pas une table.

| Colonne existante | Ce qu'elle porte |
|---|---|
| `key` | l'aliment générique (« fromage à tartiner ») |
| `value` | le produit commercial observé (« ST MORET Fromage à tartiner 400g ») |
| `reason` | la fréquence et la dernière commande (« 4/7 commandes, dernière 2026-09-01 ») |
| `updated_at` | la date de mesure |
| `active` | un récurrent retiré se désactive, il ne se supprime pas |

`shopping_preference` porte déjà la contrainte `UNIQUE(pref_type, key)`, l'endpoint de
lecture, l'endpoint d'écriture, et `load_bans()` **ignore explicitement** les `pref_type`
qu'il ne connaît pas — l'extension était prévue par construction.

Corollaire : un récurrent que le menu réclame déjà est **masqué** au calcul, par comparaison
des tokens normalisés dans les deux sens. Jamais par sous-chaîne : « lait » n'est pas couvert
par « laitue ».

## Conséquences

- Aucune migration, aucun index, aucun `CREATE TABLE` — donc aucune occasion d'oublier
  `MIGRATIONS_SQL`, le piège que le `CLAUDE.md` du projet documente en tête de section.
- `POST /api/shopping/preferences` accepte désormais `pref_type` et `value`, validés contre
  `PREF_TYPES`. Un type inconnu rend **400** plutôt que d'écrire une ligne que personne ne
  lira — c'est la même famille de panne que la table écrite-jamais-lue de #86.
- Le prix à payer est assumé : la fréquence est du **texte**, pas un couple `(n, N)`
  requêtable. Elle documente, elle ne calcule pas. Le tri régulier/occasionnel se fait au
  moment de la mesure, par le seuil ; les lignes stockées **sont** les récurrents.
- Ce qui manque reste nommé ailleurs : le recalcul de la fréquence (#107), et le produit
  précis à ajouter au panier avec son identifiant (#82).

## Alternatives rejetées

**Une table `recurrent_product`** (`name`, `label`, `n`, `total`, `last_ordered`, `source`).
Honnête sur la structure, mais elle réclamait un `CREATE TABLE` plus une entrée
`MIGRATIONS_SQL` pour trois champs dont deux sont du texte libre, et une seconde surface
d'API. Le gain structurel — `n` et `N` séparés — ne sert aucun calcul aujourd'hui : le seuil
est appliqué à la mesure, pas à la lecture.

**Un axe « provisions récurrentes » distinct**, tel que #89 le proposait à l'origine. Rejeté
dès le 2026-09-08 par arbitrage de Julien : petit-déjeuner et goûter portent des **recettes**,
comme le déjeuner et le dîner. Ce qui restait après cet arbitrage n'était plus un axe, c'était
une liste de courses d'habitude.
