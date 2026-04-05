"""
Groq Service — High-speed LLM inference for SwarmPay support agents.

Groq provides ~10x faster inference than DeepSeek for Llama/Mixtral/Gemma models.
Routes CIPHER, FORGE, SØN, BISHOP to Groq (speed + cost).
ATLAS and REGIS stay on DeepSeek/Claude (reasoning quality).

Graceful contract:
  • Returns None on any failure → caller falls back to DeepSeek
  • All calls are synchronous → use asyncio.to_thread from async context
  • Logs provider/model/latency/tokens for audit trail
"""

import logging
import os
import time
from typing import Optional

logger = logging.getLogger("swarmpay.groq")

GROQ_KEY = os.environ.get("GROQ_API_KEY", "").strip()

# Model assignments — fastest capable current Groq models (Apr 2026)
# mixtral-8x7b-32768 and gemma2-9b-it were decommissioned by Groq
GROQ_MODELS: dict[str, str] = {
    "CIPHER": "llama-3.1-8b-instant",    # fast analyst
    "FORGE":  "llama-3.1-8b-instant",    # fast synthesizer
    "SØN":    "llama-3.1-8b-instant",    # learning model (gemma2-9b-it decommissioned)
    "BISHOP": "llama-3.3-70b-versatile", # compliance — larger model for legal reasoning
}
_DEFAULT_MODEL = "llama-3.1-8b-instant"
_TIMEOUT = 25.0   # seconds


def call_groq(
    agent_name: str,
    prompt: str,
    max_tokens: int = 600,
    system: str = "",
) -> Optional[str]:
    """
    Call Groq for a support agent.
    Returns the text response string, or None if unavailable/failed.
    Synchronous — call via asyncio.to_thread.
    """
    if not GROQ_KEY:
        logger.debug("[groq] GROQ_API_KEY not set — skipping")
        return None

    model = GROQ_MODELS.get(agent_name, _DEFAULT_MODEL)

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_KEY)

        t0 = time.monotonic()
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        text = resp.choices[0].message.content
        if text:
            text = text.strip()
        tokens = resp.usage.total_tokens if resp.usage else 0

        logger.info(
            "[groq] %s · model=%s · %dms · %d tokens",
            agent_name, model, latency_ms, tokens,
        )
        return text or None

    except Exception as exc:
        logger.warning("[groq] %s failed (model=%s): %s", agent_name, model, exc)
        return None


def get_model_for_agent(agent_name: str) -> str:
    """Return the Groq model name for a given agent."""
    return GROQ_MODELS.get(agent_name, _DEFAULT_MODEL)
