"""Génération des photos de recettes (Gemini image) — PROMPT_BODY et PROMPT_VERSION montent ensemble."""

from __future__ import annotations

import base64
import io
import logging
import os
from pathlib import Path

import httpx
from PIL import Image

logger = logging.getLogger("cooking_manager.images")

PROMPT_VERSION = "1.1.0"

PROMPT_BODY = (
    "Plan rapproché serré, vue de dessus légèrement inclinée, de {plat}. "
    "Le plat REMPLIT 90 % du cadre, bord à bord. "
    "Fond uni beige très clair parfaitement lisse, sans aucun décor. "
    "AUCUN accessoire, AUCUN couvert, AUCUNE serviette, AUCUN mobilier, "
    "AUCUNE fenêtre, AUCUNE étagère, AUCUN verre, AUCUNE plante. "
    "Lumière naturelle douce et diffuse, ombre portée minimale. "
    "Rendu photographique naturel et appétissant, sans sur-saturation."
)

NEGATIVE_PROMPT = (
    "décor, accessoires, couverts, serviette, table en bois, fenêtre, étagère, "
    "verre, plante, herbes en pot, bol de sel, arrière-plan chargé, "
    "scène de cuisine, texte, logo, watermark, mains, personnes"
)

MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")
API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
ASPECT_RATIO = "16:9"

MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "/opt/cooking-manager-2/web/media/recipes"))

JPEG_QUALITY = 90
TIMEOUT_S = 180.0

CREDENTIAL_NAMES = ("cooking-gemini-key", "recipe-manager-gemini-key")


class ImageGenerationError(RuntimeError):
    """Échec de génération — remonté tel quel à l'appelant."""


def api_key() -> str | None:
    """Clé Gemini, depuis le credstore systemd puis l'environnement."""
    cred_dir = os.environ.get("CREDENTIALS_DIRECTORY")
    if cred_dir:
        for name in CREDENTIAL_NAMES:
            path = Path(cred_dir) / name
            if path.is_file():
                key = path.read_text(encoding="utf-8").strip()
                if key:
                    return key
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return key or None


def build_prompt(title: str, ingredients: list[str] | None = None) -> str:
    """Compose le prompt final. Seul {plat} varie d'une recette à l'autre."""
    plat = title.strip()
    visible = [i.strip() for i in (ingredients or []) if i and i.strip()][:5]
    if visible:
        plat += " (" + ", ".join(visible) + ")"
    return PROMPT_BODY.format(plat=plat) + "\n\nAvoid: " + NEGATIVE_PROMPT


async def generate(title: str, ingredients: list[str] | None = None) -> bytes:
    """Appelle Gemini et renvoie l'image encodée en JPEG."""
    key = api_key()
    if not key:
        raise ImageGenerationError(
            f"no Gemini API key — expected credstore {CREDENTIAL_NAMES} "
            "or GEMINI_API_KEY in the environment"
        )

    payload = {
        "contents": [{"parts": [{"text": build_prompt(title, ingredients)}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"],
            "imageConfig": {"aspectRatio": ASPECT_RATIO},
        },
    }

    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        resp = await client.post(
            f"{API_ROOT}/{MODEL}:generateContent",
            params={"key": key},
            json=payload,
        )

    if resp.status_code != 200:
        raise ImageGenerationError(f"Gemini HTTP {resp.status_code}: {resp.text[:300]}")

    raw = _extract_image(resp.json())
    return _to_jpeg(raw)


def _extract_image(data: dict) -> bytes:
    """Octets de la première partie inline ; lève si la réponse 200 ne porte aucune image."""
    for candidate in data.get("candidates") or []:
        for part in (candidate.get("content") or {}).get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    reason = (data.get("promptFeedback") or {}).get("blockReason")
    raise ImageGenerationError(f"no image in Gemini response (blockReason={reason})")


def _to_jpeg(raw: bytes) -> bytes:
    image = Image.open(io.BytesIO(raw))
    if image.mode != "RGB":
        image = image.convert("RGB")
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


def write(slug: str, jpeg: bytes, media_root: Path | None = None) -> Path:
    """Écrit l'image sous « <slug>.jpg » — la seule extension que `ingest.py` scanne (#70)."""
    root = media_root or MEDIA_ROOT
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{slug}.jpg"
    path.write_bytes(jpeg)
    return path
