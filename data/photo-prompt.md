---
title: Prompt photo — recettes
version: 1.1.0
created: 2026-08-04
updated: 2026-08-14
---

# Prompt de génération des photos de recettes

> ⚠️ **L'implémentation fait foi depuis le 2026-08-14** :
> `recipe_manager/images.py` (`PROMPT_VERSION`), exécuté par
> `POST /recipes/<slug>/generate-image` sur recipe-manager (port 8796).
> Ce fichier documente le **pourquoi** ; il ne pilote plus rien. Modifier l'un
> sans l'autre les fait diverger — et la divergence ne se voit qu'au moment où
> une image générée dans six mois ne ressemble plus aux autres.
>
> ```bash
> curl -X POST "localhost:8796/recipes/<slug>/generate-image?inline=true"
> ```
>
> Le fichier écrit vit sur la box et n'est **pas versionné** : récupérer
> `image_base64`, écrire dans `web/media/recipes/<slug>.jpg`, committer.
> La procédure manuelle NanoBanana ci-dessous reste valable en dépannage.

## Pourquoi il est versionné ici

Le design de l'app est **photo-first** : cartes sans fond, sans bordure, sans
ombre — une image posée sur du blanc. Si les photos ne forment pas une famille
visuelle cohérente, la grille se disloque et le design s'effondre.

La cohérence doit tenir **entre les recettes** *et* **dans le temps** : une
recette ajoutée dans six mois doit produire une image de la même famille. Un
prompt qui ne vit que dans l'historique d'une conversation ne le permet pas.
D'où ce fichier, dans le dépôt, versionné.

**Ne pas modifier le corps du prompt sans monter la version** — et sans
régénérer l'ensemble, sinon le parc devient hétérogène.

## Corps du prompt (invariant — v1.1, validé)

> Plan rapproché serré, vue de dessus légèrement inclinée, de {PLAT}.
> Le plat REMPLIT 90 % du cadre, bord à bord.
> Fond uni beige très clair parfaitement lisse, sans aucun décor.
> AUCUN accessoire, AUCUN couvert, AUCUNE serviette, AUCUN mobilier,
> AUCUNE fenêtre, AUCUNE étagère, AUCUN verre, AUCUNE plante.
> Lumière naturelle douce et diffuse, ombre portée minimale.
> Rendu photographique naturel et appétissant, sans sur-saturation.

**Negative prompt** (indispensable, pas optionnel) :

> décor, accessoires, couverts, serviette, table en bois, fenêtre, étagère,
> verre, plante, herbes en pot, bol de sel, arrière-plan chargé, scène de
> cuisine, texte, logo, watermark, mains, personnes

### Pourquoi cette formulation (v1.0 → v1.1)

La v1.0 disait « photographie culinaire professionnelle… fond uni… le plat
occupe 70 % du cadre ». Le modèle l'a lue comme une commande de **stylisme
culinaire** et a produit une scène complète : table en bois, fenêtre, étagère,
verre de vin, pot d'herbes, bol de sel. Superbe — et inutilisable :

- à 360 px de large sur une carte, le plat devenait minuscule ;
- les accessoires variaient à chaque génération, donc la grille se disloquait —
  exactement l'incohérence que ce fichier existe pour éviter.

La v1.1 impose le cadrage (**90 %, bord à bord**) et **énumère** ce qui est
interdit. Les interdits doivent être explicites dans le prompt *et* dans le
negative prompt : le seul negative prompt ne suffisait pas.

## Variables

- `{PLAT}` — titre de la recette, complété si besoin de 3 à 5 composants
  visibles ; c'est **la seule partie qui change**.

## Réglages

| Paramètre | Valeur |
|---|---|
| `aspect_ratio` | `16:9` (le plus proche du 19:10 des cartes ; le recadrage final se fait en CSS) |
| `model_tier` | `nb2` |
| Sortie | `web/media/recipes/<slug>.jpg` |

⚠️ **Le MCP NanoBanana tourne sur le VPS**, pas en local. Un `output_path`
Windows (`E:\…`) n'est pas interprété comme un chemin : il devient un **nom de
fichier littéral** dans `/home/automation/mcp-vps-nanobanana/`. Le dossier en
contient déjà d'anciens (`D:\HiDrive\…` de juillet) — le piège a déjà servi.

Procédure : donner un nom simple (`cm2-<slug>.jpg`), puis rapatrier.

```bash
ssh srv759970 'sudo -u mcp-run cp /home/automation/mcp-vps-nanobanana/cm2-<slug>.jpg /tmp/ && sudo chmod 644 /tmp/cm2-<slug>.jpg'
scp srv759970:/tmp/cm2-<slug>.jpg web/media/recipes/<slug>.jpg
```

## Rattachement

L'ingestion pose `photo_url = /media/recipes/<slug>.jpg` dès que le fichier
existe et qu'aucune photo n'est déjà déclarée. Rien à écrire dans le vault,
et la liaison survit à une ré-ingestion.
