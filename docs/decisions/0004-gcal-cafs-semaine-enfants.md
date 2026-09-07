# 0004 — L'event gcal "Semaine enfants" fait autorité pour la garde alternée

## Contexte

`custody_schedule.pattern = 'alternating_weeks'` calculait la présence de Léa
et Titouan depuis une date de référence figée (`2026-03-03`). Le 2026-09-07,
sans `school_period` couvrant la rentrée de septembre, ce calcul a répondu
« Julien + Clémence seuls » pour une semaine où les deux enfants étaient
réellement là — faux sans la moindre erreur.

La vraie source existe déjà : le calendrier CAFS de Julien porte un event
récurrent tout-le-jour **"Semaine enfants"**, une seule ligne pour les deux
enfants ensemble (pas de distinction par enfant).

## Décision

`custody_schedule.pattern = 'gcal'` (Léa, Titouan) : `_child_present()` lit
`cooking_manager.child_week.is_child_week(day)`, qui interroge l'API Calendar
en direct sur le calendrier CAFS — **pas de synchronisation en DB**, gcal
reste la seule source, cohérent avec la doctrine « l'agenda apporte les
exceptions, pas la trame » sauf qu'ici l'agenda EST la trame pour les
enfants.

Credential réutilisé : `~/.vdirsyncer/google_token` (refresh_token scope
`calendar` complet, service `caldav-gcal-sync` déjà en place sur srv759970,
même compte Google que le propriétaire de CAFS). Aucun nouveau consentement
OAuth.

## Alternatives rejetées

- **Synchroniser l'event vers `school_period` par ingestion périodique** —
  ajoute un délai de propagation et une DB supplémentaire à tenir à jour pour
  un event qui existe déjà, consultable en un appel.
- **Provisionner un token OAuth dédié** — isolerait le risque (si
  `caldav-gcal-sync` tourne un jour, cooking-manager n'est pas affecté), mais
  ajoute un consentement pour rien : le scope `calendar` du token existant
  est en lecture ET écriture, largement suffisant pour un `events.list`.

## Conséquences

- `is_child_week()` cache son résultat par semaine (lundi) dans le process —
  un appel réseau au plus par semaine interrogée, jamais par requête.
- Si l'event CAFS est un jour renommé ou déplacé sur un autre calendrier,
  `is_child_week()` répond `False` silencieusement (aucun garde-fou n'alerte
  sur une divergence de nom) — refs à ouvrir si ça arrive.
