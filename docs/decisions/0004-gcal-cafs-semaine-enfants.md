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

`custody_schedule.pattern = 'gcal'` (Léa, Titouan) : la présence est résolue
**à la demande** (`POST /api/child-week/sync?day=...`), jamais lue en direct
depuis `presence.py` qui reste un module domaine pur, sans I/O réseau.

- `backend/child_week_sync.py` interroge l'API Calendar (calendrier CAFS) et
  écrit le résultat dans `child_week_presence` (une ligne par lundi).
- `presence.py::_child_present()` lit `Referential.gcal_weeks`, rempli
  depuis cette table par `load_referential_from_db()` — un pur read DB.
- Une semaine **absente** de `child_week_presence` lève `ChildWeekUnknown`
  (HTTP 409 sur `/api/attendance`) plutôt que d'être assimilée à « enfants
  absents » : pas de synchronisation, pas de réponse devinée.
- Si l'event "Semaine enfants" est introuvable sur une fenêtre large (60 j
  avant/après), `sync_week()` lève `ChildWeekAmbiguous` (HTTP 422) au lieu
  d'écrire une valeur — signal absent, jamais pris pour un signal vert.

Credential réutilisé : `~/.vdirsyncer/google_token` (refresh_token scope
`calendar` complet, service `caldav-gcal-sync` déjà en place sur srv759970,
même compte Google que le propriétaire de CAFS). Aucun nouveau consentement
OAuth.

## Alternatives rejetées

- **Lecture live à chaque résolution d'attendance** (première version de
  cette décision, revertée le 2026-09-07 après revue) — violait l'architecture
  domaine-pur de `cooking_manager/` (I/O réseau dans `presence.py`), et
  couplait chaque requête `/api/attendance` à la disponibilité de l'API
  Calendar. Le cache DB écrit à la demande règle les deux.
- **Provisionner un token OAuth dédié** — isolerait le risque (si
  `caldav-gcal-sync` tourne un jour, cooking-manager n'est pas affecté), mais
  ajoute un consentement pour rien : le scope `calendar` du token existant
  est en lecture ET écriture, largement suffisant pour un `events.list`.

## Conséquences

- Une semaine de menu doit être précédée d'un `POST /api/child-week/sync`
  (ou de plusieurs, si le menu chevauche deux semaines) — sinon
  `/api/attendance` répond 409 plutôt qu'une tablée fausse.
- Si l'event CAFS est un jour renommé ou déplacé sur un autre calendrier,
  `sync_week()` répond 422 (ambigu) au lieu de se taire — la fenêtre de 60
  jours suppose l'event présent au moins une fois dans les ~4 mois
  environnants ; à revoir si le rythme de garde change.
