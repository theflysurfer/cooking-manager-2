"""Présence des enfants — lecture gcal à la demande, écrite en cache DB. Voir ADR 0004."""

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
_VDIRSYNCER_CONF = Path(os.environ.get(
    "VDIRSYNCER_CONF", str(Path.home() / "caldav-gcal-sync" / "config" / "vdirsyncer.conf"),
))
_TOKEN_URL = "https://oauth2.googleapis.com/token"

_AMBIGUITY_WINDOW_DAYS = 60

_access_token_cache: dict[str, float | str] = {}


class ChildWeekAmbiguous(Exception):
    """Aucun event "Semaine enfants" trouvé dans la fenêtre — signal absent, pas une réponse."""


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


def resolve_week(monday: date) -> bool:
    """Présence des enfants la semaine de `monday`, ou lève ChildWeekAmbiguous."""
    window_start = monday - timedelta(days=_AMBIGUITY_WINDOW_DAYS)
    window_end = monday + timedelta(days=7 + _AMBIGUITY_WINDOW_DAYS)
    mondays = _fetch_child_week_mondays(window_start, window_end)
    if not mondays:
        raise ChildWeekAmbiguous(
            f"Aucun event \"{CHILD_WEEK_EVENT_SUMMARY}\" trouvé entre "
            f"{window_start.isoformat()} et {window_end.isoformat()} sur le "
            "calendrier CAFS — vérifier que l'event existe toujours sous ce nom."
        )
    return monday in mondays


async def sync_week(pool, day: date) -> bool:
    """Résout la semaine de `day` et l'écrit dans child_week_presence."""
    monday = day - timedelta(days=day.weekday())
    present = resolve_week(monday)
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO child_week_presence (week_monday, present, synced_at)
               VALUES ($1, $2, now())
               ON CONFLICT (week_monday) DO UPDATE SET
                   present = EXCLUDED.present, synced_at = now()""",
            monday, present,
        )
    return present
