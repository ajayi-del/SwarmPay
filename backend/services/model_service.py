"""
Model Service — Unified LLM routing for SwarmPay agents.

DeepSeek Chat is the PRIMARY model for ALL tasks — reasoning, task delegation,
agent execution, and governance. Claude is reserved ONLY for REGIS challenge
adjudication or as a fallback when DEEPSEEK_API_KEY is missing.

Both calls are wrapped with try/except + retry so a single network hiccup
doesn't fail an entire task.
"""

import logging
import os
import time

import httpx
from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError

logger = logging.getLogger("swarmpay.models")

ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
DEEPSEEK_KEY   = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE  = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"
CLAUDE_MODEL   = "claude-haiku-4-5-20251001"

_MAX_RETRIES = 2
_RETRY_DELAY = 1.5   # seconds between retries

_claude_client: Anthropic | None = None


def _claude() -> Anthropic:
    global _claude_client
    if _claude_client is None:
        _claude_client = Anthropic(api_key=ANTHROPIC_KEY)
    return _claude_client


def call_claude(prompt: str, max_tokens: int = 300, system: str = "") -> str:
    """
    Call Claude Haiku with retry logic.
    Raises RuntimeError if all retries fail.
    """
    messages = [{"role": "user", "content": prompt}]
    kwargs: dict = {"model": CLAUDE_MODEL, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = _claude().messages.create(**kwargs)
            return resp.content[0].text.strip()
        except RateLimitError as exc:
            logger.warning("[claude] rate limited (attempt %d/%d): %s", attempt + 1, _MAX_RETRIES + 1, exc)
            last_exc = exc
            time.sleep(_RETRY_DELAY * (attempt + 1))
        except (APIConnectionError, APIError) as exc:
            logger.warning("[claude] API error (attempt %d/%d): %s", attempt + 1, _MAX_RETRIES + 1, exc)
            last_exc = exc
            time.sleep(_RETRY_DELAY)
        except Exception as exc:
            logger.error("[claude] unexpected error: %s", exc)
            last_exc = exc
            break

    logger.error("[claude] all retries exhausted: %s", last_exc)
    raise RuntimeError(f"Claude API unavailable: {last_exc}") from last_exc


def call_deepseek(prompt: str, max_tokens: int = 300, system: str = "") -> str:
    """
    Call DeepSeek Chat via httpx (OpenAI-compatible) with retry + Claude fallback.
    Falls back to Claude if:
      - DEEPSEEK_API_KEY is missing
      - DeepSeek is unreachable after retries
    """
    if not DEEPSEEK_KEY:
        return call_claude(prompt, max_tokens, system)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=30.0) as client:
                r = client.post(
                    f"{DEEPSEEK_BASE}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {DEEPSEEK_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": DEEPSEEK_MODEL,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": 0.7,
                    },
                )
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException as exc:
            logger.warning("[deepseek] timeout (attempt %d/%d)", attempt + 1, _MAX_RETRIES + 1)
            last_exc = exc
            time.sleep(_RETRY_DELAY)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                logger.warning("[deepseek] rate limited, retrying...")
                last_exc = exc
                time.sleep(_RETRY_DELAY * 2)
            else:
                logger.error("[deepseek] HTTP %d: %s", exc.response.status_code, exc)
                last_exc = exc
                break
        except Exception as exc:
            logger.error("[deepseek] error (attempt %d/%d): %s", attempt + 1, _MAX_RETRIES + 1, exc)
            last_exc = exc
            time.sleep(_RETRY_DELAY)

    # All DeepSeek retries exhausted — fall back to Claude
    logger.warning("[deepseek] all retries failed (%s), falling back to Claude", last_exc)
    try:
        return call_claude(prompt, max_tokens, system)
    except Exception as exc:
        logger.error("[fallback claude] also failed: %s", exc)
        return f"[Service temporarily unavailable — {type(last_exc).__name__}]"


def route(is_lead: bool, prompt: str, max_tokens: int = 300, system: str = "") -> str:
    """
    DeepSeek handles ALL agent work — lead and support alike.
    Claude is reserved exclusively for REGIS challenge adjudication.
    Falls back to Claude if DEEPSEEK_API_KEY is missing.
    """
    return call_deepseek(prompt, max_tokens, system)


def current_routing_info() -> dict:
    """Return human-readable info about current model routing."""
    primary = DEEPSEEK_MODEL if DEEPSEEK_KEY else f"{CLAUDE_MODEL} (DeepSeek key missing)"
    return {
        "primary_model":    primary,
        "governance_model": CLAUDE_MODEL,
        "deepseek_enabled": bool(DEEPSEEK_KEY),
        "deepseek_base":    DEEPSEEK_BASE,
        "note": "DeepSeek primary for all tasks; Claude reserved for REGIS challenge adjudication",
    }
