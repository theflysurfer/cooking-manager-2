"""Le drive vu par l'application : façade REST loopback de mcp-vps-auchan (#156)."""

from __future__ import annotations

import logging

import httpx

from cooking_manager.election import Offer

from .config import AUCHAN_REST_URL, AUCHAN_TIMEOUT

logger = logging.getLogger("cooking.auchan")


class DriveUnreachable(RuntimeError):
    """Le drive n'a pas répondu — jamais à confondre avec « il n'y a rien »."""


async def _call(method: str, path: str, payload: dict | None = None) -> dict:
    url = f"{AUCHAN_REST_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=AUCHAN_TIMEOUT) as client:
            response = await client.request(method, url, json=payload)
    except httpx.HTTPError as exc:
        raise DriveUnreachable(f"{method} {path} : {exc}") from exc
    if response.status_code >= 400:
        raise DriveUnreachable(
            f"{method} {path} : HTTP {response.status_code} {response.text[:200]}")
    return response.json()


async def session_status() -> dict:
    """Vérité terrain avant d'écrire : `authenticated` dit si le panier appartient au compte."""
    return await _call("GET", "/health")


async def search(query: str, limit: int = 10) -> list[Offer]:
    """Le nom nu de l'aliment → les offres du drive. Un échec lève, il ne rend pas []."""
    data = await _call("POST", "/search", {"query": query, "limit": limit})
    return [
        Offer(
            name=str(item.get("name") or ""),
            product_id=str(item.get("product_id") or ""),
            offer_id=str(item.get("offer_id") or ""),
            auchan_id=item.get("auchan_id"),
            brand=item.get("brand"),
            seller_id=item.get("seller_id"),
            stock=int(item.get("stock") or 0),
        )
        for item in data.get("results", [])
    ]


async def get_cart() -> dict:
    return await _call("GET", "/cart")


async def pin_cart(cart_id: str) -> dict:
    """Épingler le panier avant la première écriture — le self-heal le détache sinon."""
    return await _call("POST", "/cart/id", {"cart_id": cart_id})


async def add_to_cart(offer: Offer, quantity: int = 1) -> dict:
    return await _call("POST", "/cart/items", {
        "product_id": offer.product_id,
        "offer_id": offer.offer_id,
        "quantity": quantity,
        "seller_id": offer.seller_id,
    })


def cart_lines(cart: dict) -> list[dict]:
    """Les lignes d'un panier, quel que soit le nom que leur donne le drive."""
    for key in ("lines", "items", "products"):
        value = cart.get(key)
        if isinstance(value, list):
            return value
    return []


def count_for(cart: dict, offer: Offer) -> int:
    """Combien d'exemplaires de cette offre le drive dit porter — 0 si aucune ligne."""
    wanted = {offer.offer_id, offer.product_id, offer.auchan_id} - {None, ""}
    for line in cart_lines(cart):
        refs = {str(line.get(k)) for k in
                ("offer_id", "offerId", "product_id", "productId", "auchan_id")}
        if refs & wanted:
            return int(line.get("quantity") or line.get("qty") or 0)
    return 0
