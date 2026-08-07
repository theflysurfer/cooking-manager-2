"""Auchan Drive store finder — reverse-engineered from auchan.fr (2026-08-07).

Two-step flow via Auchan's CREST rendering layer:
  1. geocoding/autocomplete → HTML <li> with lat/lng in data-attributes
  2. offering-contexts → HTML store cards with storeReference + distance

Both endpoints return text/html fragments (not JSON). Parsed with selectolax.
The offering-contexts endpoint requires a connect.sid session cookie, but in
practice works without one for store discovery (non-personalized results).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from selectolax.parser import HTMLParser

_CREST_HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/150.0.0.0",
    "accept": "application/crest",
    "accept-language": "fr-FR,fr;q=0.9",
    "x-requested-with": "XMLHttpRequest",
}


@dataclass
class AuchanStore:
    name: str
    store_reference: str
    seller_id: str
    city: str
    postal_code: str
    distance_km: float
    latitude: float
    longitude: float
    channels: str = "PICK_UP"


async def find_stores(postal_code: str) -> list[AuchanStore]:
    """Find Auchan Drive stores near a postal code, sorted by distance."""
    locations = await _geocode(postal_code)
    if not locations:
        return []

    best = locations[0]
    return await _nearby(
        postal_code=best["zipcode"],
        city=best["city"],
        lat=best["latitude"],
        lng=best["longitude"],
    )


async def _geocode(postal_code: str) -> list[dict]:
    headers = {**_CREST_HEADERS, "x-crest-renderer": "geocoding-renderer"}
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://www.auchan.fr/geocoding/autocomplete",
            params={"query": postal_code},
            headers=headers,
        )
        r.raise_for_status()

    tree = HTMLParser(r.text)
    results: list[dict] = []
    for li in tree.css("li[data-latitude]"):
        attrs = li.attributes
        lat = attrs.get("data-latitude", "")
        lng = attrs.get("data-longitude", "")
        if not lat or not lng:
            continue
        results.append({
            "city": attrs.get("data-city", ""),
            "zipcode": attrs.get("data-zipcode", postal_code),
            "latitude": float(lat),
            "longitude": float(lng),
        })
    return results


_DIST_RE = re.compile(r"([\d,.]+)\s*km")


async def _nearby(
    postal_code: str, city: str, lat: float, lng: float,
) -> list[AuchanStore]:
    headers = {**_CREST_HEADERS, "x-crest-renderer": "journey-renderer"}
    params = {
        "address.zipcode": postal_code,
        "address.city": city,
        "address.country": "France",
        "location.latitude": str(lat),
        "location.longitude": str(lng),
        "accuracy": "MUNICIPALITY",
        "position": "1",
        "sellerType": "GROCERY",
        "filters.pos": "",
        "filters.slots": "",
        "filters.validStoreReferences": "",
        "channels": "PICK_UP,SHIPPING",
    }

    async with httpx.AsyncClient(follow_redirects=True) as client:
        r = await client.get(
            "https://www.auchan.fr/offering-contexts",
            params=params,
            headers=headers,
        )
        r.raise_for_status()

    tree = HTMLParser(r.text)
    stores: list[AuchanStore] = []

    for card in tree.css(".journeyPosItem, [class*='journey-offering-context__wrapper']"):
        ref_input = card.css_first("input[name='storeReference']")
        if not ref_input:
            continue
        store_ref = ref_input.attributes.get("value", "")
        if not store_ref:
            continue

        seller_input = card.css_first("input[name='sellerId']")
        seller_id = (seller_input.attributes.get("value") or "") if seller_input else ""

        channels_input = card.css_first("input[name='channels']")
        channels = (channels_input.attributes.get("value") or "") if channels_input else ""

        name_el = card.css_first(".place-pos__name, [class*='place-pos__name']")
        name = name_el.text(strip=True) if name_el else ""

        dist_el = card.css_first("[class*='pos-distance']")
        distance_km = 0.0
        if dist_el:
            dm = _DIST_RE.search(dist_el.text(strip=True))
            if dm:
                distance_km = float(dm.group(1).replace(",", "."))

        card_lat = float(card.attributes.get("data-lat") or lat)
        card_lng = float(card.attributes.get("data-lng") or lng)
        card_zipcode = card.attributes.get("data-zipcode") or postal_code
        card_city = card.attributes.get("data-city") or city

        stores.append(AuchanStore(
            name=name,
            store_reference=store_ref,
            seller_id=seller_id,
            city=card_city,
            postal_code=card_zipcode,
            distance_km=distance_km,
            latitude=card_lat,
            longitude=card_lng,
            channels=channels,
        ))

    seen: set[str] = set()
    deduped: list[AuchanStore] = []
    for s in stores:
        if s.store_reference not in seen:
            seen.add(s.store_reference)
            deduped.append(s)
    deduped.sort(key=lambda s: s.distance_km)
    return deduped
