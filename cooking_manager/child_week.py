"""Présence des enfants — source de vérité : l'event gcal "Semaine enfants".

Remplace le repli `alternating_weeks` de `presence.py` (constante figée au
2026-03-03, jamais recalée) : la garde alternée réelle vit dans le calendrier
CAFS de Julien, event récurrent tout-le-jour "Semaine enfants". Un
`school_period` absent (ex. rentrée non déclarée) faisait retomber sur ce
repli constant et annonçait Clémence seule à table — faux sans la moindre
erreur (incident 2026-09-07).

Lecture directe de l'API Calendar, jamais synchronisée en DB : le
`refresh_token` réutilisé (`~/.vdirsyncer/google_token`, scope `calendar`
complet) appartient au sync CalDAV↔Google déjà en place sur le VPS — même
compte Google que celui qui possède CAFS, aucun nouveau consentement.
"""

from __future__ import annotations

import configparser
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

CAFS_CALENDAR_ID = "d41639fb3d8e5e9162d4c1e9708acf530267cf0f9843f7c0f0d3c6029d2a603d@group.calendar.google.com"
CHILD_WEEK_EVENT_SUMMARY = "Semaine enfants"

_TOKEN_FILE = Path(os.environ.get("VDIRSYNCER_GOOGLE_TOKEN", str(Path.home() / ".vdirsyncer" / "google_token")))
# client_id/secret vivent dans la conf vdirsyncer, pas dans le fichier token
# (qui ne porte que access_token/refresh_token/scope).
_VDIRSYNCER_CONF = Path(os.environ.get(
    "VDIRSYNCER_CONF", str(Path.home() / "caldav-gcal-sync" / "config" / "vdirsyncer.conf"),
))
_TOKEN_URL = "https://oauth2.googleapis.com/token"

_access_token_cache: dict[str, float | str] = {}
_week_cache: dict[date, bool] = {}


def _get_access_token() -> str:
    now = time.time()
    cached = _access_token_cache
    if cached.get("token") and float(cached.get("expires_at", 0)) > now + 30:
        return str(cached["token"])

    stored = json.loads(_TOKEN_FILE.read_text())
    conf = configparser.ConfigParser()
    conf.read(_VDIRSYNCER_CONF)
    google_section = conf["storage google"]
    resp = httpx.post(
        _TOKEN_URL,
        data={
            "client_id": google_section["client_id"].strip('"'),
            "client_secret": google_section["client_secret"].strip('"'),
            "refresh_token": stored["refresh_token"],
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    cached["token"] = data["access_token"]
    cached["expires_at"] = now + data["expires_in"]
    return str(data["access_token"])


def _fetch_child_week_mondays(time_min: date, time_max: date) -> set[date]:
    """Lundis des semaines couvertes par l'event "Semaine enfants" sur la plage."""
    token = _get_access_token()
    resp = httpx.get(
        f"https://www.googleapis.com/calendar/v3/calendars/{CAFS_CALENDAR_ID}/events",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "timeMin": f"{time_min.isoformat()}T00:00:00Z",
            "timeMax": f"{time_max.isoformat()}T00:00:00Z",
            "q": CHILD_WEEK_EVENT_SUMMARY,
            "singleEvents": "true",
            "orderBy": "startTime",
        },
        timeout=10,
    )
    resp.raise_for_status()
    mondays: set[date] = set()
    for event in resp.json().get("items", []):
        if event.get("summary") != CHILD_WEEK_EVENT_SUMMARY:
            continue
        start_raw = event.get("start", {}).get("date") or event.get("start", {}).get("dateTime")
        if not start_raw:
            continue
        start_day = date.fromisoformat(start_raw[:10])
        mondays.add(start_day - timedelta(days=start_day.weekday()))
    return mondays


def is_child_week(day: date) -> bool:
    """Les enfants sont-ils présents la semaine de `day`, selon gcal CAFS ?

    Résultat mis en cache par semaine (lundi) — un appel réseau au plus par
    semaine interrogée dans le process, jamais par requête.
    """
    monday = day - timedelta(days=day.weekday())
    if monday in _week_cache:
        return _week_cache[monday]

    mondays = _fetch_child_week_mondays(monday, monday + timedelta(days=7))
    result = monday in mondays
    _week_cache[monday] = result
    return result
