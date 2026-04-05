"""
Perplexity Service — Real-time web research for ATLAS.

Uses Perplexity's sonar-large-online model which searches the internet live.
Returns text + source citations. Falls back gracefully when key absent.

Graceful contract:
  • Returns None on any failure → ATLAS falls back to Firecrawl then DeepSeek
  • Synchronous (httpx.Client) — use asyncio.to_thread from async context
  • httpx is already in requirements — no new dependency
"""

import logging
import os
from typing import Optional, Dict, List

import httpx

logger = logging.getLogger("swarmpay.perplexity")

PERPLEXITY_KEY = os.environ.get("PERPLEXITY_API_KEY", "").strip()
_BASE_URL = "https://api.perplexity.ai"
_MODEL = "llama-3.1-sonar-large-128k-online"
_TIMEOUT = 30.0


def research(query: str, agent_name: str = "ATLAS") -> Optional[Dict]:
    """
    Real-time web research via Perplexity Sonar Online.
    Returns {text, sources, provider, model} or None if unavailable/failed.
    Synchronous — call via asyncio.to_thread.
    """
    if not PERPLEXITY_KEY:
        logger.debug("[perplexity] PERPLEXITY_API_KEY not set — skipping")
        return None

    payload = {
        "model": _MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    f"You are {agent_name}, a specialist research agent. "
                    "Provide factual, sourced information with concrete data points. "
                    "Always include inline citations and structure your response clearly."
                ),
            },
            {"role": "user", "content": query},
        ],
        "return_citations": True,
        "return_images": False,
        "search_recency_filter": "week",
        "max_tokens": 800,
    }

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            r = client.post(
                f"{_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {PERPLEXITY_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            r.raise_for_status()
            data = r.json()

        text: str = data["choices"][0]["message"]["content"]
        citations: List[str] = data.get("citations", [])

        logger.info("[perplexity] %s · %d citations · model=%s", agent_name, len(citations), _MODEL)
        return {
            "text": text,
            "sources": citations[:5],
            "provider": f"perplexity/{_MODEL}",
            "model": _MODEL,
        }

    except httpx.HTTPStatusError as exc:
        logger.warning("[perplexity] HTTP %d: %s", exc.response.status_code, exc)
        return None
    except Exception as exc:
        logger.warning("[perplexity] research failed: %s", exc)
        return None
