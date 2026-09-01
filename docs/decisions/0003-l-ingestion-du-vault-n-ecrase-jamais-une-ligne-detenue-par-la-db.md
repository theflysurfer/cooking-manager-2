---
numero: 0003
titre: L'ingestion du vault n'écrase jamais une ligne détenue par la DB
statut: accepté
date: 2026-09-01
concerne:
  - backend/ingest.py
  - backend/app.py
  - backend/cooking_mcp.py
---

# 0003 — L'ingestion du vault n'écrase jamais une ligne détenue par la DB

## Contexte

`pantry_item.source` dit d'où vient une ligne : `vault`, `receipt`, `voice`, `manual`, `coach`.
L'ingestion du vault faisait un upsert `ON CONFLICT (name_normalized, section) DO UPDATE` sans
aucune condition sur `source`, et repositionnait `source = 'vault'` au passage. Toute ligne
partageant la clé avec le Markdown était donc écrasée, puis rendue supprimable par le
`DELETE … WHERE source = 'vault'` qui suit.

La docstring de la fonction affirmait pourtant que les lignes non-vault « ne sont jamais
touchées ». Rien ne l'exécutait : c'était une promesse écrite à côté d'un code qui faisait
l'inverse.

Symétriquement, `update_pantry_item` ne modifiait pas `source`. Une correction appliquée par le
Coach ou par la voix sur une ligne d'origine vault restait estampillée `vault`, et se faisait
donc annuler à l'ingestion suivante — sans erreur, sans trace.

Si le piège n'a jamais explosé, c'est seulement parce que la clé d'upsert est trop faible pour
entrer en collision (cf. ADR 0002). Corriger l'identité sans corriger la propriété aurait armé le
piège.

## Décision

L'upsert d'ingestion porte `WHERE pantry_item.source = 'vault'`. Une ligne détenue par une autre
source n'est ni modifiée, ni re-tamponnée.

Quand une ligne du Markdown est ainsi masquée par une ligne détenue par la DB, l'ingestion
**émet un avertissement nommant l'article et son détenteur**. Le conflit devient visible au lieu
d'être arbitré en silence.

Toute écriture déclare sa provenance : `PantryItemUpdate` porte un champ `source`, et les outils
MCP `pantry_add` / `pantry_update` l'envoient (`coach` par défaut). Écrire, c'est prendre
possession de la ligne.

## Conséquences

Une correction faite dans `Garde-manger.md` sur un article déjà repris en main par la DB n'a plus
d'effet. C'est le comportement voulu, mais il inverse l'intuition de qui édite le vault : d'où
l'avertissement, qui est la seule chose qui l'en informe.

`RETURNING id` ne renvoie plus rien lorsque le garde rejette le conflit. Tout appelant doit
traiter ce cas ; l'ignorer produirait une exception à la première collision réelle.

Les appelants qui ne passent pas de `source` conservent celui de la ligne existante. Le
comportement des voies historiques est inchangé, mais un nouvel appelant qui oublie ce champ
écrira sans prendre possession, et se fera annuler comme avant.

## Alternatives écartées

**Faire gagner l'écriture la plus récente** en comparant `updated_at` : cette colonne date
l'écriture, pas l'observation. Une ré-ingestion massive réestampille toutes les lignes du vault
du jour même et leur ferait gagner tous les arbitrages.

**Interdire l'ingestion dès qu'un conflit existe** : bloquerait l'ingestion entière pour un seul
article divergent, et pousserait à contourner le garde.

**Laisser le vault gagner et documenter le piège** : c'est l'état de départ. Un piège documenté
dans une docstring que rien n'exécute a produit exactement la panne qu'il prétendait décrire.
