"""Speech-to-text + LLM intent resolver for Cooking Manager.

Pipeline: audio bytes → Deepgram (transcription) → Ollama cloud (intent JSON)
→ action executor (calls existing API endpoints internally).

Pattern from Family Manager (family_dashboard/stt.py), adapted to cooking domain.
"""

import json
import logging
import re

import httpx

from .config import (
    DEEPGRAM_API_KEY,
    DEEPGRAM_LANGUAGE,
    DEEPGRAM_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    OLLAMA_API_KEY,
    OLLAMA_MODEL,
    OLLAMA_URL,
)

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Tu es l'assistant vocal de Cooking Manager, une app de cuisine familiale.
Tu reçois une phrase transcrite et tu la traduis en UNE action JSON.

Actions possibles :

1. adjust_servings — changer le nombre de portions d'un repas
   {"action": "adjust_servings", "delta": +1}  ou  {"action": "adjust_servings", "servings": 6}

2. product_blacklist — ne plus acheter un produit
   {"action": "product_blacklist", "product": "saumon fumé Auchan", "reason": "trop salé"}

3. recipe_note — ajouter une remarque à la recette en cours
   {"action": "recipe_note", "note": "ajouter du citron à la fin"}

4. recipe_edit_step — modifier une étape de la recette en cours
   {"action": "recipe_edit_step", "step": 2, "modification": "ajouter 1 c.à.s d'huile d'olive"}

5. meal_feedback — retour sur un repas (appréciation)
   {"action": "meal_feedback", "convive": "Titouan", "liked": false, "dish": "curry coco"}

6. pantry_leftover — déclarer un reste à réutiliser
   {"action": "pantry_leftover", "ingredient": "lentilles", "quantity": "300g", \
"source_meal": "ce midi"}

7. swap_recipe — changer la recette d'un créneau du menu
   {"action": "swap_recipe", "slot": "dinner", "day": "mercredi", "recipe": "salade niçoise"}

8. search_recipe — chercher une recette
   {"action": "search_recipe", "query": "poulet"}

Si la phrase ne correspond à aucune action, renvoie :
   {"action": "unknown", "text": "<phrase originale>"}

Réponds UNIQUEMENT avec le JSON, sans texte autour, sans markdown.
"""


async def transcribe(audio_bytes: bytes, content_type: str = "audio/webm") -> str:
    """Transcribe audio via Deepgram prerecorded API."""
    if not DEEPGRAM_API_KEY:
        raise RuntimeError("DEEPGRAM_API_KEY not configured")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.deepgram.com/v1/listen",
                headers={
                    "Authorization": f"Token {DEEPGRAM_API_KEY}",
                    "Content-Type": content_type,
                },
                params={
                    "model": DEEPGRAM_MODEL,
                    "language": DEEPGRAM_LANGUAGE,
                    "smart_format": "true",
                    "punctuate": "true",
                },
                content=audio_bytes,
            )
            r.raise_for_status()
    except httpx.TimeoutException:
        log.error("Deepgram timeout after 30s")
        raise RuntimeError("Deepgram timeout") from None
    data = r.json()

    channels = data.get("results", {}).get("channels", [])
    if not channels:
        return ""
    alternatives = channels[0].get("alternatives", [])
    if not alternatives:
        return ""
    return alternatives[0].get("transcript", "")


async def _interpret_groq(transcript: str) -> str:
    """Resolve transcript via Groq (OpenAI-compatible, ~<1s)."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "response_format": {"type": "json_object"},
                    "reasoning_effort": "none",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": transcript},
                    ],
                },
            )
    except httpx.TimeoutException:
        log.error("Groq timeout after 15s (model=%s)", GROQ_MODEL)
        raise RuntimeError(f"Groq timeout (model={GROQ_MODEL})") from None
    if not r.is_success:
        log.error("Groq %d: %s (model=%s)", r.status_code, r.text[:200], GROQ_MODEL)
        raise RuntimeError(f"Groq error {r.status_code} (model={GROQ_MODEL})")
    return r.json()["choices"][0]["message"]["content"]


async def _interpret_ollama(transcript: str) -> str:
    """Resolve transcript via Ollama cloud (fallback, slower)."""
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/chat",
                headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"},
                json={
                    "model": OLLAMA_MODEL,
                    "stream": False,
                    "format": "json",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": transcript},
                    ],
                },
            )
    except httpx.TimeoutException:
        log.error("Ollama timeout after 120s (model=%s)", OLLAMA_MODEL)
        raise RuntimeError(f"Ollama timeout (model={OLLAMA_MODEL})") from None
    if not r.is_success:
        log.error("Ollama %d: %s (model=%s)", r.status_code, r.text[:200], OLLAMA_MODEL)
        raise RuntimeError(f"Ollama error {r.status_code} (model={OLLAMA_MODEL})")
    return r.json().get("message", {}).get("content", "{}")


async def interpret(transcript: str) -> dict:
    """Resolve transcript to a structured intent. Groq first, Ollama fallback."""
    if not transcript.strip():
        return {"action": "unknown", "text": ""}

    if GROQ_API_KEY:
        raw = await _interpret_groq(transcript)
    elif OLLAMA_API_KEY:
        raw = await _interpret_ollama(transcript)
    else:
        raise RuntimeError("No LLM API key configured (GROQ_API_KEY or OLLAMA_API_KEY)")

    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.warning("LLM returned non-JSON: %s", raw[:200])
        return {"action": "unknown", "text": transcript, "raw_llm": raw[:200]}


async def process_audio(audio_bytes: bytes, content_type: str = "audio/webm") -> dict:
    """Full pipeline: transcribe → interpret → return result."""
    transcript = await transcribe(audio_bytes, content_type)
    if not transcript:
        return {"transcript": "", "intent": {"action": "unknown", "text": ""}}

    intent = await interpret(transcript)
    return {"transcript": transcript, "intent": intent}
