# 0008 — La clé d'appariement du garde-manger : ce qu'elle retire, et ce qu'elle vise

- **Statut** : accepté
- **Date** : 2026-09-08
- **Supersède** : rien. Complète l'ADR 0003 (flexion des termes) côté courses.

## Contexte

Le différentiel de courses du menu du 7 au 14 septembre sortait **23 lignes à
acheter pour environ 15 aliments réels**. Trois causes distinctes, toutes muettes.

**Le nom portait sa découpe.** « comté, en dés » (160 g) et « comté, râpé
grossièrement » (120 g) étaient deux besoins ; un panier aurait acheté deux fois
du comté. Idem pour les patates douces, l'ail, le citron, l'oignon jaune, les
lentilles vertes, les poivrons, la mâche-roquette, et trois lignes de bouillon.

**Le pluriel séparait aussi.** « oignon jaune » et « oignons jaunes » ne se
rencontraient pas, et aucun des deux ne trouvait le stock.

**L'appariement exigeait une séquence contiguë.** « mélange mâche et roquette »
ne rencontrait pas « Mélange **de** mâche et roquette » : un mot-outil suffisait
à faire racheter un sachet déjà au frigo.

## Décision

### 1. `normalize_name` retire la découpe et le pluriel, jamais un état

La docstring de la fonction portait déjà la règle : *ne retirer QUE ce qui ne
change jamais l'identité du produit*. Une découpe n'a jamais changé l'identité
d'un aliment. Un état, si.

- **Retiré** — un segment après virgule qui commence par une préparation
  déclarée (`PREPARATIONS` : ciselé, râpé, émincé, égoutté, en dés, en
  tranches…), puis la marque du pluriel, mot à mot.
- **Conservé** — « sèches », « surgelés », « fraîche », « entier » : lentilles
  sèches ≠ cuites (facteur 3 sur les macros), crème fraîche ≠ crème.
- **Écarté** : couper à la première virgule. Plus simple, et ça viole la règle.

Les invariables en `-s` sont une **liste fermée** (`INVARIABLE_IN_S`), pas une
règle morphologique : « frais » n'est pas le pluriel de « frai ». Le `-x` n'est
jamais touché — « noix » ne doit pas devenir « noi ».

### 2. Un appariement approchant est un dernier repli, à sens unique

Après l'égalité exacte et l'inclusion de séquence, tous les mots **porteurs** du
besoin doivent se retrouver dans l'article, ordre libre, mots-outils écartés.

Le sens est asymétrique et il compte : **le stock peut être plus précis que le
besoin** (« Knorr Bouillon de Légumes » répond à « bouillon de légumes »),
jamais l'inverse — « lait de coco » ne se satisfait pas de « lait ». Un faux
« tu en as » fait sauter un achat, et ça ne se découvre qu'en cuisine.

### 3. Un alias vise un NOM, et prime sur toute heuristique

`pantry_alias` visait un `pantry_item_id` en `ON DELETE CASCADE`. L'ingestion
supprime les articles de source `vault` absents du fichier : **sept alias sur dix
ont disparu** entre leur création et cette session, sans une erreur.

La cible devient `target_normalized`, un nom qui survit à la recréation de
l'article. La FK subsiste en `ON DELETE SET NULL`, comme simple commodité.

L'alias est consulté **avant** toute heuristique : c'est une décision humaine
(« origan séché » EST le « Hello Fresh Origan » du placard, rien dans le nom du
stock ne le dit), et elle ne se laisse pas déborder par un appariement approchant.

## Conséquences

- Mesuré sur le menu de la semaine : **23 lignes à acheter → 12**, sans qu'aucun
  besoin réel ne disparaisse.
- **Une clé stockée est figée au jour où elle a été écrite.** Changer
  `normalize_name` désaligne `pantry_item.name_normalized` et `pantry_alias` :
  `POST /api/pantry/renormalize` (avec `?dry_run=true` d'abord) est désormais
  obligatoire après tout changement, et rejouable.
- Le prix : ajouter une préparation ou un invariable demande de toucher une
  liste. Un terme oublié reste silencieux — d'où un test par cas, dans les deux
  directions.
- Deux défauts ont été révélés en chemin, invisibles tant que les doublons
  existaient : `build_needs` additionnait en unités brutes (« 800 g + 1 kg =
  801 kg »), et `Pantry.find` faisait confiance à son appelant pour normaliser.
