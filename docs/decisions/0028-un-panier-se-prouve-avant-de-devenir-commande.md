---
numero: 0028
titre: Un panier se prouve avant de devenir commande
statut: accepté
date: 2026-09-21
concerne:
  - backend/app.py
  - cooking_manager/bans.py
---

# 0028 — Un panier se prouve avant de devenir commande

## Contexte

Le panier Auchan se remplit par une suite d'appels `grocery_add_to_cart`, puis
`grocery_create_order` le convertit en commande. Après cette conversion, son contenu sort de
portée : `grocery_get_cart` rend 0 article, et `grocery_orders` ne montre que les commandes
**confirmées** — une commande créée sans créneau ni paiement n'y figure pas. `grocery_order_detail`
exige `order_id` **et** `arom_id`, que seule l'historique fournit.

La commande `1f900f71` du 2026-09-20 (46 lignes, 212,16 €) a été créée sans que
`POST /api/shopping/persist-cart` soit appelé. `shopping_session` ne portait alors que deux lignes,
du 2026-08-04 et du 2026-09-11.

Le lendemain, deux retours de Julien sur cette commande — « il y avait 6 paquets de parmesan » et
« il manque des carottes ? » — n'ont pu être instruits ni l'un ni l'autre. La liste de courses
réclamait bien `carottes` (`absent`, marqué épuisé) et `parmesan râpé` (`absent`), mais ce qui est
réellement entré au panier n'existe nulle part de notre côté. Les deux ajouts ont rendu un succès :
`grocery_add_to_cart` répond `ok` sans garantir la quantité obtenue.

## Décision

Un panier ne devient une commande qu'après deux gestes, dans cet ordre :

1. **`POST /api/shopping/persist-cart`** écrit les lignes et leurs quantités en base. Si cette
   écriture échoue, `grocery_create_order` **n'est pas appelé**.
2. **Réconciliation** : `grocery_get_cart` est relu et confronté ligne à ligne à la liste voulue.
   Le diff — manquants, quantités divergentes, intrus — est montré à Julien, et la commande ne
   part pas sans son accord.

## Conséquences

- Un retour sur une commande devient instruisible : on sait ce qu'on a demandé et ce que le panier
  portait réellement.
- Le report au garde-manger après retrait se fait depuis la base, sans dépendre de l'historique
  Auchan.
- **Une panne de la base empêche désormais de commander.** C'est le coût assumé du gate : Julien a
  explicitement préféré ce risque à celui d'une commande dont on ne sait rien. Le contournement
  existe et reste manuel — commander depuis le site.
- Deux appels de plus par commande, et un aller-retour humain sur le diff. La commande n'est plus
  un geste d'un seul tenant.
- La réconciliation ne corrige rien d'elle-même : elle montre. Une correction automatique
  effacerait un ajout que Julien aurait fait à la main.

## Alternatives écartées

- **Persister sans bloquer** (écrire, puis commander quoi qu'il arrive) : l'échec d'écriture serait
  silencieux, et on retrouverait exactement l'angle mort du 2026-09-20 — une commande sans trace,
  qui se lit comme une commande tracée.
- **Ne rien persister et relire la commande après retrait** : c'est la situation actuelle. Les
  lignes finissent par être lisibles, mais seulement après paiement — donc aucun contrôle avant.
- **Réconcilier en corrigeant automatiquement les écarts** (`grocery_update_quantity`) : moins
  d'allers-retours, mais l'agent effacerait sans le savoir un ajout humain délibéré.
- **Vérifier le panier après chaque ajout** : 46 lignes = 46 appels supplémentaires, et cela ne dit
  rien des intrus arrivés par un autre chemin.
