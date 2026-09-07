# 0009 — Du besoin de recette à la quantité d'achat

- **Statut** : accepté
- **Date** : 2026-09-07
- **Suit** : [0008 — la clé d'appariement du garde-manger](0008-la-cle-d-appariement-du-garde-manger.md)
- **Issues** : #80, #81, #82

## Contexte

Entre le menu et le panier, deux traductions manquaient, et chacune produisait
une erreur qui ne se voyait pas.

**Un aliment portait deux besoins.** `build_needs` consolidait sur le nom
normalisé seul. Or chaque fiche nomme son ingrédient dans le contexte de sa
recette : « bouillon de légumes **chaud** », « lentilles vertes **sèches (poids
cuit ~300 g)** », « **trio de** poivrons en lanières ». Les deux moitiés
tombaient de part et d'autre du différentiel — l'une trouvait le stock, l'autre
non — et la ligne ressortait `absent` pour un aliment présent.

**Un besoin n'était pas une commande.** Sur le menu du 2026-09-07, 28 lignes sur
54 portaient une unité qu'aucun magasin ne lit : `c.s.`, `c.c.`, `gousse`,
`pièce`, `botte`. Envoyée telle quelle, la ligne demande « 2 cuillères à soupe
de moutarde ».

## Décision

### 1. La consolidation rapproche deux libellés, sous deux conditions

Le comparateur est celui de `Pantry.find` — inclusion de mots porteurs, mots-outils
ignorés — et il ne s'applique que :

- **à famille d'unité égale.** « 2 sachets » et « 2 poignées » de mâche ne
  s'additionnent pas ; les fondre produirait un chiffre faux qui a l'air juste.
- **quand un nom est contenu dans l'autre.** Deux mots communs ne suffisent
  pas : « lentilles corail » et « lentilles vertes » sont deux aliments.

Le nom retenu est le plus générique (le plus court). Les libellés absorbés
restent dans `merged_from` : **une fusion se voit**, elle ne fait pas disparaître
une ligne en silence.

### 2. Une dose n'est pas une quantité d'achat

`purchase.py` classe chaque besoin en quatre :

| `kind` | Règle |
|---|---|
| `mesure` | g, kg, ml, cl, l — déjà commandable |
| `comptable` | pièce, boîte, sachet… — arrondi **vers le haut** |
| `dose` | c.s., c.c., gousse, pincée… — **1 conditionnement**, quelle que soit la quantité |
| `non_resolu` | ni unité ni quantité déductible — déclaré, jamais supposé |

### 3. Le calcul s'arrête à « un conditionnement »

Il dit *qu'il en faut un*, jamais *lequel*. Un pot de moutarde fait 370 g ici et
200 g ailleurs : le format vendu appartient à l'enseigne, pas au domaine. Cette
frontière est la raison d'être de #82 (mémoire produit : `ingredient_normalized`
+ `store` + EAN + conditionnement).

## Conséquences

- 54 → 50 besoins, 8 → 7 absents sur le menu mesuré ; « lentilles vertes » ne
  ressort plus absent alors qu'elles sont en stock.
- 49 lignes sur 50 portent une quantité qu'un magasin comprend.
- Un arrondi va **toujours** vers le haut : manquer coûte plus cher qu'avoir un
  peu trop, et le manque ne se découvre qu'en cuisine.
- La liste de courses porte deux champs de plus : `merged_from` et `purchase`.

## Écarté

- **Fusionner sur un chevauchement partiel** (« trio de poivrons » et « poivrons
  rouges » partagent un mot). Un faux rapprochement fait sauter un achat ; deux
  lignes en double coûtent moins cher qu'un dîner sans son ingrédient.
- **Convertir les doses en grammes** avec les densités de `nutrition.py`. C'est
  exact pour une macro, faux pour un achat : personne ne commande 30 g de
  moutarde.
- **Stocker un conditionnement par aliment dans le domaine.** Il n'existe pas
  d'aliment « moutarde en pot de 370 g » — il existe un produit, dans un
  magasin, à une date.
