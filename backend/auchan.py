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


BROWSE_HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/150.0.0.0",
    "accept-language": "fr-FR,fr;q=0.9",
    "cookie": "auchan_delivery_choice=DRIVE; auchan_store_reference=874",
}

_PIPE_RE = re.compile(r"Pipe\.(?:start|end)\(\d+\)")


@dataclass
class SearchResult:
    name: str
    brand: str
    auchan_id: str
    price: str
    url: str


async def search_products(query: str, page: int = 1) -> list[SearchResult]:
    """Search Auchan Drive products via SSR scraping."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        r = await client.get(
            "https://www.auchan.fr/recherche",
            params={"text": query, "page": page},
            headers=BROWSE_HEADERS,
        )
        r.raise_for_status()

    tree = HTMLParser(r.text)
    results: list[SearchResult] = []

    for link in tree.css("a[href*='/pr-']"):
        href = link.attributes.get("href") or ""
        id_match = re.search(r"/pr-([A-Z0-9]+)", href)
        if not id_match:
            continue

        raw_text = _PIPE_RE.sub("", link.text(strip=True))
        brand_el = link.css_first("strong")
        brand = brand_el.text(strip=True) if brand_el else ""
        name = raw_text.replace(brand, "", 1).strip() if brand else raw_text

        price_el = link.css_first("[class*='price']")
        price = price_el.text(strip=True) if price_el else ""

        url = f"https://www.auchan.fr{href}" if href.startswith("/") else href
        results.append(SearchResult(
            name=name, brand=brand, auchan_id=id_match.group(1),
            price=price, url=url,
        ))

    seen = set()
    deduped = []
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
    detail = ProductDetail(url=auchan_url)

    # Extract auchan_id from URL
    m = re.search(r"/pr-([A-Z0-9]+)", auchan_url)
    if m:
        detail.auchan_id = m.group(1)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        r = await client.get(auchan_url, headers=BROWSE_HEADERS)
        r.raise_for_status()

    tree = HTMLParser(r.text)

    # Title
    title = tree.css_first("h1")
    if title:
        detail.name = title.text(strip=True)

    # Brand
    brand_el = tree.css_first("[class*='product-description'] strong, [class*='brand']")
    if brand_el:
        detail.brand = brand_el.text(strip=True)

    # Nutriscore — Auchan no longer displays it as an image;
    # enriched later via Open Food Facts if EAN is found

    # Photo
    img = tree.css_first("[class*='product-thumbnail'] img, [class*='product-media'] img")
    if img:
        detail.photo_url = img.attributes.get("src") or ""

    # Price
    price_el = tree.css_first("[class*='price--big'], [class*='product-price']")
    if price_el:
        txt = price_el.text(strip=True)
        pm = _PRICE_RE.search(txt)
        if pm:
            detail.price = float(pm.group(1).replace(",", "."))
        pkm = _PRICE_KG_RE.search(txt)
        if pkm:
            detail.price_per_kg = float(pkm.group(1).replace(",", "."))

    # Nutrition table
    for row in tree.css("table tr"):
        cells = row.css("td, th")
        if len(cells) >= 2:
            label = cells[0].text(strip=True).lower()
            value = cells[1].text(strip=True)
            if label and "information" not in label and "pour" not in label:
                detail.nutrition[label] = value

    # Ingredients, allergens, EAN, and characteristics from feature groups
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

    # Extract allergens from CAPITALIZED words in ingredients text
    # (Auchan marks allergens in uppercase per EU regulation)
    if detail.ingredients and not detail.allergens:
        caps = re.findall(r"\b([A-ZÀÂÉÈÊËÎÏÔÙÛÜÇ]{2,}(?:\s+[A-ZÀÂÉÈÊËÎÏÔÙÛÜÇ]{2,})*)\b",
                          detail.ingredients)
        if caps:
            seen: set[str] = set()
            unique: list[str] = []
            for c in caps:
                low = c.lower()
                if low not in seen:
                    seen.add(low)
                    unique.append(c.capitalize())
            detail.allergens = ", ".join(unique)

    # Description
    desc_el = tree.css_first("[class*='product-description__content']")
    if desc_el:
        detail.description = desc_el.text(strip=True)[:500]

    # Weight from title
    wm = re.search(r"(\d+[x×]\d+\s*g|\d+\s*[gk]g?|\d+\s*[mc]l)", detail.name, re.IGNORECASE)
    if wm:
        detail.weight = wm.group(1)

    # Enrich from Open Food Facts if we have an EAN and are missing data
    if detail.ean and (not detail.nutriscore or not detail.allergens):
        await _enrich_from_openfoodfacts(detail)

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

    return await scrape_product_detail(best.url)
