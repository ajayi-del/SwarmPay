"""
Model Service — Unified LLM routing for SwarmPay agents.

Lead agents  → Claude Haiku (complex reasoning, character, coordination)
Support agents → DeepSeek Chat (routine tasks, cost saving ~80%)

DeepSeek is OpenAI-compatible — we call it via httpx directly,
no extra packages needed.
"""

import os
import httpx
from anthropic import Anthropic

ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
DEEPSEEK_KEY   = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE  = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"
CLAUDE_MODEL   = "claude-haiku-4-5-20251001"

_claude_client: Anthropic | None = None


def _claude() -> Anthropic:
    global _claude_client
    if _claude_client is None:
        _claude_client = Anthropic(api_key=ANTHROPIC_KEY)
    return _claude_client


def call_claude(prompt: str, max_tokens: int = 300, system: str = "") -> str:
    """Call Claude Haiku. Returns response text."""
    messages = [{"role": "user", "content": prompt}]
    kwargs: dict = {"model": CLAUDE_MODEL, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system
    resp = _claude().messages.create(**kwargs)
    return resp.content[0].text.strip()


def call_deepseek(prompt: str, max_tokens: int = 300, system: str = "") -> str:
    """Call DeepSeek Chat via httpx (OpenAI-compatible). Returns response text."""
    if not DEEPSEEK_KEY:
        # Fallback to Claude if no DeepSeek key
        return call_claude(prompt, max_tokens, system)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

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


def route(is_lead: bool, prompt: str, max_tokens: int = 300, system: str = "") -> str:
    """
    Route to the right model based on agent role:
    - Lead agent  → Claude Haiku (nuanced, costly)
    - Support agent → DeepSeek Chat (fast, cheap)
    """
    if is_lead:
        return call_claude(prompt, max_tokens, system)
    return call_deepseek(prompt, max_tokens, system)


def current_routing_info() -> dict:
    """Return human-readable info about current model routing."""
    return {
        "lead_model": CLAUDE_MODEL,
        "support_model": DEEPSEEK_MODEL if DEEPSEEK_KEY else f"{CLAUDE_MODEL} (DeepSeek key missing)",
        "deepseek_enabled": bool(DEEPSEEK_KEY),
        "deepseek_base": DEEPSEEK_BASE,
    }
