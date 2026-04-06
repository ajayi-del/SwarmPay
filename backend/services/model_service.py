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
import threading
import time

import httpx
from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError

logger = logging.getLogger("swarmpay.models")

# Token cost per token (USD)
TOKEN_COSTS: dict[str, float] = {
    "deepseek-chat":              0.00000014,   # $0.14/1M
    "llama-3.1-8b-instant":       0.0,          # Groq free
    "llama-3.3-70b-versatile":    0.0,          # Groq free
    "claude-haiku-4-5-20251001":  0.00000025,   # $0.25/1M
    "duckduckgo":                 0.0,
    "fallback":                   0.0,
}

# Thread-safe in-memory token log (no PocketBase dep)
_log_lock = threading.Lock()
_token_log: list[dict] = []   # [{task_id, agent, model, tokens, cost_usd, ts}]

_deepseek_last_tokens: list[int] = [0]  # thread-unsafe but fine for estimating


def record_tokens(task_id: str, agent: str, model: str, tokens: int) -> None:
    """Record token usage for a call. Graceful — never raises."""
    if not tokens or not task_id:
        return
    cost = tokens * TOKEN_COSTS.get(model, 0.0)
    with _log_lock:
        _token_log.append({
            "task_id": task_id,
            "agent":   agent,
            "model":   model,
            "tokens":  tokens,
            "cost_usd": cost,
            "ts":      time.time(),
        })


def get_session_summary(task_id: str) -> dict:
    """
    Aggregate token usage for a task into summary dict.
    Returns empty-safe structure if no data.
    """
    with _log_lock:
        records = [r for r in _token_log if r["task_id"] == task_id]

    if not records:
        return {
            "total_tokens": 0, "total_cost_usd": 0.0,
            "by_provider": {}, "by_agent": [],
        }

    by_agent: dict[str, dict] = {}
    for r in records:
        a = r["agent"]
        if a not in by_agent:
            by_agent[a] = {"agent": a, "model": r["model"], "tokens": 0, "cost_usd": 0.0}
        by_agent[a]["tokens"]   += r["tokens"]
        by_agent[a]["cost_usd"] += r["cost_usd"]

    by_provider: dict[str, dict] = {}
    for r in records:
        provider = _model_to_provider(r["model"])
        if provider not in by_provider:
            by_provider[provider] = {"tokens": 0, "cost_usd": 0.0, "free": TOKEN_COSTS.get(r["model"], 1) == 0.0}
        by_provider[provider]["tokens"]   += r["tokens"]
        by_provider[provider]["cost_usd"] += r["cost_usd"]

    total_tokens   = sum(r["tokens"]   for r in records)
    total_cost_usd = sum(r["cost_usd"] for r in records)

    return {
        "total_tokens":   total_tokens,
        "total_cost_usd": total_cost_usd,
        "by_provider":    by_provider,
        "by_agent":       list(by_agent.values()),
    }


def _model_to_provider(model: str) -> str:
    if model.startswith("llama") or model.startswith("gemma") or model.startswith("mixtral"):
        return "groq"
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("deepseek"):
        return "deepseek"
    return "other"

ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
DEEPSEEK_KEY   = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE  = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"
CLAUDE_MODEL   = "claude-haiku-4-5-20251001"

# Agents routed to Groq (speed + cost savings vs DeepSeek)
GROQ_AGENTS = {"CIPHER", "FORGE", "SØN", "BISHOP"}

_MAX_RETRIES = 2
_RETRY_DELAY = 1.5   # seconds between retries

_claude_client: Anthropic | None = None


def _claude() -> Anthropic:
    global _claude_client
    if _claude_client is None:
        _claude_client = Anthropic(api_key=ANTHROPIC_KEY)
    return _claude_client


from services.retry_decorator import with_retry

@with_retry(max_retries=_MAX_RETRIES, base_delay=_RETRY_DELAY)
def call_claude(prompt: str, max_tokens: int = 300, system: str = "") -> str:
    """
    Call Claude Haiku with robust exponential backoff.
    """
    messages = [{"role": "user", "content": prompt}]
    kwargs: dict = {"model": CLAUDE_MODEL, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system

    resp = _claude().messages.create(**kwargs)
    return resp.content[0].text.strip()


def call_deepseek(prompt: str, max_tokens: int = 300, system: str = "") -> str:
    """
    Call DeepSeek Chat via httpx (OpenAI-compatible) with robust exponential backoff.
    Falls back to Claude if:
      - DEEPSEEK_API_KEY is missing
      - DeepSeek is unreachable after all retries
    """
    if not DEEPSEEK_KEY:
        return call_claude(prompt, max_tokens, system)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    @with_retry(max_retries=_MAX_RETRIES, base_delay=_RETRY_DELAY)
    def _attempt_call():
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
            content = data["choices"][0]["message"]["content"].strip()
            # Capture usage for token tracking
            usage = data.get("usage", {})
            _deepseek_last_tokens[0] = int(usage.get("total_tokens", 0) or
                                            usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0))
            return content

    try:
        return _attempt_call()
    except Exception as exc:
        # All DeepSeek retries exhausted — fall back to Claude
        logger.warning("[deepseek] all retries failed (%s), falling back to Claude", exc)
        try:
            return call_claude(prompt, max_tokens, system)
        except Exception as fallback_exc:
            logger.error("[fallback claude] also failed: %s", fallback_exc)
            return f"[Service temporarily unavailable — {type(fallback_exc).__name__}]"


def route(is_lead: bool, prompt: str, max_tokens: int = 300, system: str = "") -> str:
    """
    DeepSeek handles ALL agent work — lead and support alike.
    Claude is reserved exclusively for REGIS challenge adjudication.
    Falls back to Claude if DEEPSEEK_API_KEY is missing.
    Preserved for backward compatibility — new code uses route_for_agent().
    """
    return call_deepseek(prompt, max_tokens, system)


def route_for_agent(
    agent_name: str,
    prompt: str,
    max_tokens: int = 600,
    system: str = "",
    task_id: str = "",
) -> tuple[str, str]:
    """
    Route LLM call based on agent name. Returns (text, provider_label).

    Routing priority:
      CIPHER / FORGE / SØN / BISHOP → Groq (fast, cheap) → DeepSeek fallback
      ATLAS / REGIS / others        → DeepSeek → Claude fallback

    provider_label format: "groq/model-name" | "deepseek/deepseek-chat"
    Used in output JSON for audit trail and UI display.
    """
    if agent_name in GROQ_AGENTS:
        try:
            from services.groq_service import call_groq, get_model_for_agent
            groq_result = call_groq(agent_name, prompt, max_tokens, system)
            if groq_result:
                # call_groq returns (text, tokens) tuple
                if isinstance(groq_result, tuple):
                    text, tokens = groq_result
                else:
                    text, tokens = groq_result, 0
                if task_id and tokens:
                    record_tokens(task_id, agent_name, get_model_for_agent(agent_name), tokens)
                return text, f"groq/{get_model_for_agent(agent_name)}"
        except Exception as exc:
            logger.warning("[model] groq routing failed for %s: %s", agent_name, exc)

    # Fall back to DeepSeek
    _deepseek_last_tokens[0] = 0
    text = call_deepseek(prompt, max_tokens, system)
    if task_id:
        tokens = _deepseek_last_tokens[0]
        if tokens:
            record_tokens(task_id, agent_name, DEEPSEEK_MODEL, tokens)
    return text, "deepseek/deepseek-chat"


def current_routing_info() -> dict:
    """Return human-readable info about current model routing."""
    groq_key = os.environ.get("GROQ_API_KEY", "")
    primary = DEEPSEEK_MODEL if DEEPSEEK_KEY else f"{CLAUDE_MODEL} (DeepSeek key missing)"
    return {
        "primary_model":    primary,
        "governance_model": CLAUDE_MODEL,
        "deepseek_enabled": bool(DEEPSEEK_KEY),
        "deepseek_base":    DEEPSEEK_BASE,
        "groq_enabled":     bool(groq_key),
        "groq_agents":      list(GROQ_AGENTS),
        "note": (
            "Groq (Llama/Gemma/Mixtral) for CIPHER/FORGE/SØN/BISHOP; "
            "DeepSeek for ATLAS/REGIS; Claude for governance adjudication"
        ),
    }
