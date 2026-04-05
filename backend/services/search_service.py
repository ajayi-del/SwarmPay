"""
Search Service — Free real-time web search for ATLAS using DuckDuckGo.

No API key required. Uses duckduckgo-search (DDGS) — synchronous, free forever.
Returns top results with titles, URLs, and snippets.

Graceful contract:
  • Returns None on any failure → ATLAS falls back to Firecrawl then DeepSeek
  • Synchronous — call via asyncio.to_thread from async context
  • Logs result count and latency for audit trail
"""

import logging
import time
from typing import Optional, Dict, List

logger = logging.getLogger("swarmpay.search")

_MAX_RESULTS = 5
_TIMEOUT = 20


def research(query: str, agent_name: str = "ATLAS") -> Optional[Dict]:
    """
    Web search via DuckDuckGo (no API key, free forever).
    Returns {text, sources, provider, model} or None on failure.
    Synchronous — call via asyncio.to_thread.
    """
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.debug("[search] duckduckgo-search not installed — skipping")
        return None

    try:
        t0 = time.monotonic()
        results: List[Dict] = []

        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=_MAX_RESULTS, timelimit="m"):
                results.append(r)

        latency_ms = int((time.monotonic() - t0) * 1000)

        if not results:
            logger.debug("[search] no results for query: %s", query[:60])
            return None

        # Build a readable summary from snippets
        snippets = []
        sources: List[str] = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            if href:
                sources.append(href)
            if body:
                snippets.append(f"• {title}: {body}" if title else f"• {body}")

        text = "\n".join(snippets[:_MAX_RESULTS])

        logger.info(
            "[search] %s · %d results · %dms",
            agent_name, len(results), latency_ms,
        )
        return {
            "text": text,
            "sources": sources[:5],
            "provider": "duckduckgo/ddgs",
            "model": "ddgs-text",
        }

    except Exception as exc:
        logger.warning("[search] DuckDuckGo search failed: %s", exc)
        return None
