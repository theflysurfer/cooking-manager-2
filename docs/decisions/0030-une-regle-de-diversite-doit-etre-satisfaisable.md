---
numero: 0030
titre: Une règle de diversité doit être satisfaisable
statut: accepté
date: 2026-09-21
concerne:
  - cooking_manager/preferences.py
---

# 0030 — Une règle de diversité doit être satisfaisable

## Contexte

La règle `rotate famille de protéine` plafonnait chaque famille à 2 repas par semaine. Six familles
— viande, volaille, poisson, fruits de mer, œuf, légumineuse — soit 12 repas porteurs de protéine
au maximum.

La semaine compte 14 déjeuners et dîners, et depuis le 2026-09-20 elle compte aussi 14
petits-déjeuners et goûters, soit 28 créneaux. Mesure sur la semaine 21-27 : 20 repas portent une
famille de protéine (`légumineuse 7 · œuf 5 · poisson 4 · volaille 2 · viande 1 · fruits de mer 1`).
La règle était franchie avant qu'aucun menu ne soit composé, et quatre familles sur six
apparaissaient en rouge.

Le 2026-09-20, l'arbitrage avait été de ne rien changer et de corriger le détecteur de protéine
(#111 consignait la décision de fond comme ouverte). Le 2026-09-21, mis devant la question du
périmètre, Julien a tranché l'inverse de ce que proposait l'issue : « il est absolument
indispensable de tout suivre, petits déj et goûters compris ».

## Décision

Le comptage porte sur **tous les créneaux**, et le plafond passe de 2 à **6 repas par semaine et
par famille**. Le périmètre ne rétrécit pas ; c'est le seuil qui s'aligne sur ce que la semaine
contient.

## Conséquences

- La règle redevient satisfaisable : 6 familles × 6 = 36 ≥ 28 créneaux.
- Elle redevient informative. Sur la semaine 21-27, mesuré après application : `breached: true` sur
  **la seule légumineuse** (7), là où quatre familles étaient rouges avant. Le signal désigne un
  vrai déséquilibre — lentilles, pois chiches, haricots rouges et chili la même semaine.
- **Le seuil est permissif** : à 6, une famille doit occuper plus d'un repas sur cinq de la semaine
  pour se signaler. Une dérive modérée passera sous le radar.
- Le plafond vaut pour toutes les familles indistinctement. Manger de la viande 6 fois et des
  légumineuses 6 fois déclenche le même silence, alors que les deux ne s'équivalent pas.

## Alternatives écartées

- **Garder 2 et ne compter que déjeuner et dîner** : corrigeait l'œuf (les petits-déjeuners sortant
  du compte) mais laissait légumineuse et poisson franchis en permanence — et surtout, cela revenait
  à cesser de suivre ce que Julien mange le matin, ce qu'il a refusé explicitement.
- **Plafond à 4 ou 5** : plus exigeant, mais l'œuf du petit-déjeuner quasi quotidien produirait un
  rouge presque chaque semaine — le défaut même qu'on corrige, un voyant rouge permanent qu'on
  apprend à ignorer.
- **Un seuil par famille** (viande 2, volaille 3, poisson 4, œuf 6, légumineuse 6) : le plus juste,
  et le seul qui dirait que viande et légumineuse ne se valent pas. Écarté pour son coût : le
  schéma ne porte **qu'une** valeur pour toute la règle, et il faudrait fixer six chiffres en plus
  d'écrire le code.
- **Ne rien changer et marquer le dépassement comme structurel** : la règle resterait impossible,
  avec une étiquette expliquant pourquoi. Un garde-fou qui s'excuse de ne pas fonctionner.
