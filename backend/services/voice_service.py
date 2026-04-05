"""
Voice Service — ElevenLabs text-to-speech for key governance moments.

Design contract:
  • Returns None silently when ELEVENLABS_API_KEY is absent (graceful degradation)
  • All functions are synchronous (called via asyncio.to_thread)
  • speak_to_b64() is the primary API — returns base64 for JSON transport
  • Text is capped at 800 chars to control latency and token cost

Voice assignments match agent persona characteristics:
  REGIS  → Daniel  (deep, authoritative, British)
  CIPHER → Adam    (calm, analytical)
  ATLAS  → Arnold  (strong, Germanic)
  FORGE  → Josh    (powerful, energetic)
  SØN    → Sam     (young, clear, Scandinavian)
  BISHOP → Callum  (solemn, formal)
"""

import base64
import logging
import os
from typing import Optional

logger = logging.getLogger("swarmpay.voice")

AGENT_VOICES: dict[str, str] = {
    "REGIS":  "onwK4e9ZLuTAKqWW03F9",   # Daniel — deep authoritative
    "CIPHER": "pNInz6obpgDQGcFmaJgB",   # Adam   — calm analytical
    "ATLAS":  "VR6AewLTigWG4xSOukaG",   # Arnold — strong Germanic
    "FORGE":  "TxGEqnHWrfWFTfGW9XjX",  # Josh   — powerful energetic
    "SØN":    "yoZ06aMxZJJ28mfd3POQ",   # Sam    — young clear
    "BISHOP": "N2lVS1w4EtoT3dr4eOWO",  # Callum — solemn formal
}

_MAX_CHARS = 800
_MODEL     = "eleven_multilingual_v2"


def _api_key() -> str:
    return os.environ.get("ELEVENLABS_API_KEY", "")


def speak(agent: str, text: str) -> Optional[bytes]:
    """
    Generate audio bytes for the given agent and text.
    Returns None when ElevenLabs is unconfigured or an error occurs.
    """
    api_key = _api_key()
    if not api_key:
        return None
    if not text or not text.strip():
        return None
    try:
        from elevenlabs.client import ElevenLabs
        client = ElevenLabs(api_key=api_key)
        voice_id = AGENT_VOICES.get(agent, AGENT_VOICES["REGIS"])
        chunks = client.generate(
            text=text[:_MAX_CHARS],
            voice=voice_id,
            model=_MODEL,
        )
        return b"".join(chunks)
    except Exception as exc:
        logger.warning("[voice] %s speak failed: %s", agent, exc)
        return None


def speak_to_b64(agent: str, text: str) -> Optional[str]:
    """
    Generate audio and return as base64-encoded UTF-8 string for JSON transport.
    Returns None when voice is unavailable.
    """
    audio = speak(agent, text)
    if audio:
        return base64.b64encode(audio).decode("utf-8")
    return None
