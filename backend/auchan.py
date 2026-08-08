"""Auchan Drive API client — reverse-engineered from browser network calls.

Endpoints discovered 2026-08-03 via HydraSpecter network monitoring.
Auth: Keycloak JWT from compte.auchan.fr, refreshed via browser cookies.
Product detail: SSR scraping (no API endpoint for nutrition/ingredients).
"""

import json
import re
from dataclasses import dataclass, field

import httpx
from selectolax.parser import HTMLParser

API_BASE = "https://api.auchan.fr"
GRAVITEE_KEY = "29df4324-b153-4939-9f43-24b153e9393d"
CLIENT_ID = "lark-checkout-front"
CONSENT_ID = "7cf2b6b6-860d-4c0c-baf2-50a111bf308f"


@dataclass
class AuchanClient:
    token: str
    cart_id: str | None = None

    @property
    def _headers(self) -> dict:
        return {
            "authorization": f"Bearer {self.token}",
            "x-gravitee-api-key": GRAVITEE_KEY,
            "client-id": CLIENT_ID,
            "content-type": "application/json;charset=UTF-8",
            "accept": "application/json",
            "accept-language": "fr-FR",
        }

    async def get_cart(self) -> dict:
        async with httpx.AsyncClient() as client:
            if self.cart_id:
                url = f"{API_BASE}/checkout/v1/carts/{self.cart_id}"
            else:
                url = f"{API_BASE}/checkout/v1/carts/mine"
            r = await client.get(
                url, headers=self._headers,
                params={"consentId": CONSENT_ID},
            )
            r.raise_for_status()
            data = r.json()
            if not self.cart_id:
                self.cart_id = data["id"]
            return data

    async def remove_from_cart(self, product_id: str) -> dict:
        """Remove a product from cart by its productId.

        Fetches the cart to find the internal item ID, then sends
        desiredQuantity=0 to the items endpoint.
        """
        cart = await self.get_cart()
        item = next(
            (i for i in cart["items"] if i["productId"] == product_id),
            None,
        )
        if not item:
            return {"error": "product not found in cart", "product_id": product_id}

        payload = [{
            "id": item["id"],
            "productId": item["productId"],
            "offerId": item["offerId"],
            "desiredQuantity": 0,
        }]

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{API_BASE}/checkout/v1/carts/{self.cart_id}/items",
                headers=self._headers,
                params={"consentId": CONSENT_ID},
                content=json.dumps(payload),
            )
            r.raise_for_status()
            return r.json()

    async def update_quantity(self, product_id: str, quantity: int) -> dict:
        """Update quantity of a product in cart."""
        cart = await self.get_cart()
        item = next(
            (i for i in cart["items"] if i["productId"] == product_id),
            None,
        )
        if not item:
            return {"error": "product not found in cart", "product_id": product_id}

        payload = [{
            "id": item["id"],
            "productId": item["productId"],
            "offerId": item["offerId"],
            "desiredQuantity": quantity,
        }]

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{API_BASE}/checkout/v1/carts/{self.cart_id}/items",
                headers=self._headers,
                params={"consentId": CONSENT_ID},
                content=json.dumps(payload),
            )
            r.raise_for_status()
            return r.json()

    async def add_to_cart(
        self, product_id: str, offer_id: str, quantity: int = 1,
    ) -> dict:
        """Add a product to cart."""
        payload = [{
            "productId": product_id,
            "offerId": offer_id,
            "desiredQuantity": quantity,
        }]

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{API_BASE}/checkout/v1/carts/{self.cart_id}/items",
                headers=self._headers,
                params={"consentId": CONSENT_ID},
                content=json.dumps(payload),
            )
            r.raise_for_status()
            return r.json()


_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/150.0.0.0"

_PIPE_RE = re.compile(r"Pipe\.(?:start|end)\(\d+\)")


@dataclass
class SearchResult:
    name: str
    brand: str
    auchan_id: str
    price: str
    url: str
    image_url: str = ""


_IMG_SIZE_RE = re.compile(r"width=\d+&height=\d+")


class AuchanSession:
    """SSR session with journey — required for prices since mid-2026.

    Prices are gated behind a server-side journey tied to connect.sid.
    Without it, seller_type=NONE and all prices show "Afficher le prix".
    Flow: GET homepage (→ connect.sid) → POST /journey/update → inject
    lark-* cookies manually (JS-only cookies, never in Set-Cookie).
    """

    def __init__(
        self,
        store_reference: str = "874",
        seller_id: str = "899a3667-614e-49f6-9203-1e03810d6120",
        city: str = "Aubagne",
        postal_code: str = "13400",
        latitude: str = "43.292438",
        longitude: str = "5.570303",
    ):
        self.store_reference = store_reference
        self.seller_id = seller_id
        self.city = city
        self.postal_code = postal_code
        self.latitude = latitude
        self.longitude = longitude
        self._client: httpx.AsyncClient | None = None
        self._initialized = False

    async def _ensure_init(self) -> None:
        if self._initialized:
            return

        self._client = httpx.AsyncClient(follow_redirects=True)
        await self._client.get(
            "https://www.auchan.fr/",
            headers={"user-agent": _UA, "accept-language": "fr-FR"},
        )

        r = await self._client.post(
            "https://www.auchan.fr/journey/update",
            data={
                "offeringContext.seller.id": self.seller_id,
                "offeringContext.storeReference": self.store_reference,
                "offeringContext.sellerType": "GROCERY",
                "offeringContext.deliveryChannel": "DRIVE",
                "offeringContext.channels": "PICK_UP",
                "address.city": self.city,
                "address.zipcode": self.postal_code,
                "location.latitude": self.latitude,
                "location.longitude": self.longitude,
            },
            headers={
                "user-agent": _UA,
                "x-requested-with": "XMLHttpRequest",
                "content-type": "application/x-www-form-urlencoded",
            },
        )
        r.raise_for_status()
        jdata = r.json()
        journey_id = jdata["id"]
        active_seller = jdata["activeContexts"][0]["context"]["seller"]["id"]

        self._client.cookies.set("lark-journey", journey_id, domain="www.auchan.fr")
        self._client.cookies.set("lark-sellerId", active_seller, domain=".auchan.fr")
        self._client.cookies.set("lark-deliveryChannel", "DRIVE", domain=".auchan.fr")
        self._client.cookies.set("lark-sellerType", "GROCERY", domain=".auchan.fr")
        self._client.cookies.set("auchan_store_reference", self.store_reference, domain=".auchan.fr")
        self._client.cookies.set("auchan_delivery_choice", "DRIVE", domain=".auchan.fr")

        self._initialized = True

    def _export_cookies(self) -> dict[str, str]:
        assert self._client is not None
        return {name: value for name, value in self._client.cookies.items()}

    async def search(self, query: str, page: int = 1) -> list[SearchResult]:
        await self._ensure_init()
        from .stealth import fetch_html
        url = f"https://www.auchan.fr/recherche?text={query}&page={page}"
        html = await fetch_html(url, cookies=self._export_cookies())
        return _parse_search_results(html)

    async def scrape_detail(self, auchan_url: str) -> "ProductDetail":
        await self._ensure_init()
        from .stealth import fetch_html
        html = await fetch_html(auchan_url, cookies=self._export_cookies())
        return _parse_product_detail(html, auchan_url)


_default_session: AuchanSession | None = None


def _get_session() -> AuchanSession:
    global _default_session
    if _default_session is None:
        _default_session = AuchanSession()
    return _default_session


async def search_products(query: str, page: int = 1) -> list[SearchResult]:
    """Search Auchan Drive products via SSR scraping (with journey session)."""
    return await _get_session().search(query, page)


def _parse_search_results(html_text: str) -> list[SearchResult]:
    tree = HTMLParser(html_text)
    results: list[SearchResult] = []

    for link in tree.css("a[href*='/pr-']"):
        href = link.attributes.get("href") or ""
        id_match = re.search(r"/pr-([A-Z0-9]+)", href)
        if not id_match:
            continue

        source_el = link.css_first("picture source[alt]")
        if source_el:
            name = (source_el.attributes.get("alt") or "").strip()
        else:
            raw_text = _PIPE_RE.sub("", link.text(strip=True))
            brand_el = link.css_first("strong")
            brand_txt = brand_el.text(strip=True) if brand_el else ""
            name = raw_text.replace(brand_txt, "", 1).strip() if brand_txt else raw_text

        brand_el = link.css_first("strong")
        brand = brand_el.text(strip=True) if brand_el else ""

        meta_img = link.css_first("meta[itemprop='image']")
        image_url = ""
        if meta_img:
            raw_url = meta_img.attributes.get("content") or ""
            image_url = _IMG_SIZE_RE.sub("width=200&height=200", raw_url)

        container = link.parent
        price_meta = (
            link.css_first("meta[itemprop='price']")
            or (container.css_first("meta[itemprop='price']") if container else None)
        )
        if price_meta:
            price = (price_meta.attributes.get("content") or "") + " €"
        else:
            price_el = link.css_first("[class*='price']")
            price = price_el.text(strip=True) if price_el else ""

        url = f"https://www.auchan.fr{href}" if href.startswith("/") else href
        results.append(SearchResult(
            name=name, brand=brand, auchan_id=id_match.group(1),
            price=price, url=url, image_url=image_url,
        ))

    seen: set[str] = set()
    deduped: list[SearchResult] = []
    for r in results:
        if r.auchan_id not in seen:
            seen.add(r.auchan_id)
            deduped.append(r)
    return deduped


@dataclass
class ProductDetail:
    name: str = ""
    brand: str = ""
    auchan_id: str = ""
    ean: str = ""
    price: float | None = None
    price_per_kg: float | None = None
    weight: str = ""
    nutriscore: str = ""
    nutrition: dict = field(default_factory=dict)
    ingredients: str = ""
    allergens: str = ""
    description: str = ""
    characteristics: dict = field(default_factory=dict)
    photo_url: str = ""
    url: str = ""


_PRICE_RE = re.compile(r"([\d,]+)\s*€")
_PRICE_KG_RE = re.compile(r"([\d,]+)\s*€\s*/\s*kg")


async def scrape_product_detail(auchan_url: str) -> ProductDetail:
    """Scrape a product page for nutrition, ingredients, and characteristics."""
    return await _get_session().scrape_detail(auchan_url)


def _parse_product_detail(html_text: str, auchan_url: str) -> ProductDetail:
    detail = ProductDetail(url=auchan_url)

    m = re.search(r"/pr-([A-Z0-9]+)", auchan_url)
    if m:
        detail.auchan_id = m.group(1)

    tree = HTMLParser(html_text)

    title = tree.css_first("h1")
    if title:
        detail.name = title.text(strip=True)

    brand_el = tree.css_first("[class*='product-description'] strong, [class*='brand']")
    if brand_el:
        detail.brand = brand_el.text(strip=True)

    img = tree.css_first("[class*='product-thumbnail'] img, [class*='product-media'] img")
    if img:
        detail.photo_url = img.attributes.get("src") or ""

    price_meta = tree.css_first("meta[itemprop='price']")
    if price_meta:
        raw = price_meta.attributes.get("content") or ""
        try:
            detail.price = float(raw)
        except ValueError:
            pass
    if detail.price is None:
        price_el = tree.css_first("[class*='price--big'], [class*='product-price']")
        if price_el:
            txt = price_el.text(strip=True)
            pm = _PRICE_RE.search(txt)
            if pm:
                detail.price = float(pm.group(1).replace(",", "."))

    price_kg_el = tree.css_first("[class*='price--big'], [class*='product-price']")
    if price_kg_el:
        pkm = _PRICE_KG_RE.search(price_kg_el.text(strip=True))
        if pkm:
            detail.price_per_kg = float(pkm.group(1).replace(",", "."))

    for row in tree.css("table tr"):
        cells = row.css("td, th")
        if len(cells) >= 2:
            label = cells[0].text(strip=True).lower()
            value = cells[1].text(strip=True)
            if label and "information" not in label and "pour" not in label:
                detail.nutrition[label] = value

    for group in tree.css("[class*='feature-group-wrapper']"):
        label_el = group.css_first("[class*='feature-label']")
        values_el = group.css_first("[class*='feature-values']")
        if not label_el:
            continue
        label = label_el.text(strip=True).lower()
        value = values_el.text(strip=True) if values_el else ""
        if "ingrédient" in label:
            detail.ingredients = re.sub(r"^Ingrédients\s*:\s*", "", value).strip()
        elif "allergène" in label:
            detail.allergens = re.sub(r"^Allergènes\s*:\s*", "", value).strip()
        elif "réf" in label and "ean" in label:
            ean_match = re.search(r"(\d{8,13})\s*$", value)
            if ean_match:
                detail.ean = ean_match.group(1)
        elif label and value:
            detail.characteristics[label_el.text(strip=True)] = value

    if detail.ingredients and not detail.allergens:
        caps = re.findall(r"\b([A-ZÀÂÉÈÊËÎÏÔÙÛÜÇ]{2,}(?:\s+[A-ZÀÂÉÈÊËÎÏÔÙÛÜÇ]{2,})*)\b",
                          detail.ingredients)
        if caps:
            seen_caps: set[str] = set()
            unique: list[str] = []
            for c in caps:
                low = c.lower()
                if low not in seen_caps:
                    seen_caps.add(low)
                    unique.append(c.capitalize())
            detail.allergens = ", ".join(unique)

    desc_el = tree.css_first("[class*='product-description__content']")
    if desc_el:
        detail.description = desc_el.text(strip=True)[:500]

    wm = re.search(r"(\d+[x×]\d+\s*g|\d+\s*[gk]g?|\d+\s*[mc]l)", detail.name, re.IGNORECASE)
    if wm:
        detail.weight = wm.group(1)

    return detail


_OFF_ALLERGEN_FR: dict[str, str] = {
    "en:gluten": "Gluten",
    "en:milk": "Lait",
    "en:eggs": "Œufs",
    "en:nuts": "Fruits à coque",
    "en:peanuts": "Arachides",
    "en:soybeans": "Soja",
    "en:celery": "Céleri",
    "en:mustard": "Moutarde",
    "en:sesame-seeds": "Sésame",
    "en:fish": "Poisson",
    "en:crustaceans": "Crustacés",
    "en:molluscs": "Mollusques",
    "en:lupin": "Lupin",
    "en:sulphur-dioxide-and-sulphites": "Sulfites",
}


async def _enrich_from_openfoodfacts(detail: ProductDetail) -> None:
    """Fill nutriscore/allergens/ingredients from Open Food Facts (free API)."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"https://world.openfoodfacts.org/api/v2/product/{detail.ean}",
                params={"fields": "nutriscore_grade,allergens_tags,ingredients_text_fr"},
                headers={"User-Agent": "CookingManager/2.0 (contact@cooking.app)"},
            )
            if not r.is_success:
                return
    except httpx.TimeoutException:
        return
    data = r.json()
    product = data.get("product", {})
    if not product:
        return

    if not detail.nutriscore:
        grade = product.get("nutriscore_grade", "")
        if grade and grade in "abcde":
            detail.nutriscore = grade.upper()

    if not detail.allergens:
        tags: list[str] = product.get("allergens_tags", [])
        if tags:
            detail.allergens = ", ".join(
                _OFF_ALLERGEN_FR.get(t, t.replace("en:", "").replace("-", " ").capitalize())
                for t in tags
            )

    if not detail.ingredients:
        off_ingredients = product.get("ingredients_text_fr", "")
        if off_ingredients:
            detail.ingredients = off_ingredients


async def find_product_detail(product_name: str, brand: str | None = None) -> ProductDetail | None:
    """Resolve a cart product name to its full catalog detail (nutrition, ingredients,
    allergens, nutriscore) via public search + SSR scrape.

    Cart items only expose an internal cart-item UUID (productId/offerId), not the
    public catalog auchan_id (e.g. C1224996) needed to fetch the product page. This
    re-finds the product by name in the public catalog to bridge that gap.
    """
    results = await search_products(product_name)
    if not results:
        return None

    best = results[0]
    if brand:
        for r in results:
            if r.brand and r.brand.lower() == brand.lower():
                best = r
                break

    detail = await scrape_product_detail(best.url)
    if detail.ean and (not detail.nutriscore or not detail.allergens):
        await _enrich_from_openfoodfacts(detail)
    return detail
