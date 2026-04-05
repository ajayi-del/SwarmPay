"""
Background Scans — Autonomous agent intelligence gathering.

Three periodic scans run without LLM calls or payment processing:
  • REGIS  every  5 min — Solana DeFi yield signals
  • CIPHER every 15 min — Yield farming opportunity classification
  • ATLAS  every 30 min — Solana news sentiment + risk alerts

Pattern: DuckDuckGo search → HuggingFace zero-shot classify → Audit log
No payments, no LLM tokens consumed. Pure signal gathering.
"""

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger("swarmpay.scans")


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo search — free, no API key. Returns list of {title, snippet, url}."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, timelimit="d"))
        return results
    except Exception as exc:
        logger.warning("[scan ddg] %s", exc)
        return []


def _hf_classify(text: str, labels: list[str]) -> Optional[str]:
    """
    HuggingFace zero-shot classification — free with API key.
    Returns the top label or None on failure.
    """
    hf_key = os.environ.get("HUGGINGFACE_API_KEY", "").strip()
    if not hf_key:
        return None
    try:
        from huggingface_hub import InferenceClient
        client = InferenceClient(token=hf_key)
        result = client.zero_shot_classification(
            text[:512],
            labels,
            multi_label=False,
        )
        if result and isinstance(result, list):
            first = result[0]
            return getattr(first, "label", None) or (first.get("label") if isinstance(first, dict) else None)
        return None
    except Exception as exc:
        logger.warning("[scan hf] %s", exc)
        return None


async def _write_audit(event_type: str, entity_id: str, message: str, metadata: dict = None):
    """Write to PocketBase audit_log (non-blocking)."""
    try:
        from services.pocketbase import PocketBaseService
        pb = PocketBaseService()
        await asyncio.to_thread(pb.create, "audit_log", {
            "event_type": event_type,
            "entity_id": entity_id,
            "message": message,
            "metadata": metadata or {},
        })
    except Exception as exc:
        logger.warning("[scan audit] %s", exc)


async def _telegram_alert(message: str):
    """Send Telegram alert (non-blocking, best-effort)."""
    try:
        from services.telegram_service import send_message
        await asyncio.to_thread(send_message, message)
    except Exception:
        pass


# ── REGIS Scan (every 5 minutes) ──────────────────────────────────────────────

async def regis_scan():
    """
    REGIS intelligence sweep: DeFi yield signals on Solana.
    Classifies opportunities as high/medium/low yield.
    Writes findings to audit log and updates REGIS brain file.
    No LLM calls, no payments.
    """
    logger.info("[regis_scan] starting sweep")
    try:
        results = await asyncio.to_thread(
            _ddg_search, "Solana DeFi yield APR today Raydium Orca Jupiter", 5
        )
        if not results:
            logger.info("[regis_scan] no results")
            return

        # Classify top result
        top = results[0]
        snippet = f"{top.get('title','')} {top.get('body', top.get('snippet',''))}"
        label = await asyncio.to_thread(
            _hf_classify, snippet,
            ["high yield opportunity", "medium yield", "low yield", "risky investment"]
        ) or "medium yield"

        # Build message
        source_name = top.get("title", "DeFi source")[:60]
        msg = (
            f"REGIS SCAN: {source_name} — "
            f"Signal: {label.upper()} · "
            f"{snippet[:120]}…"
        )

        await _write_audit(
            "task_submitted",  # gold colour in audit log
            "REGIS",
            msg,
            {"scan": "regis", "label": label, "sources": len(results), "query": "Solana DeFi yield"},
        )

        # Update REGIS brain file
        brain_path = os.path.join(os.path.dirname(__file__), "..", "regis_brain.md")
        try:
            brain_path = os.path.realpath(brain_path)
            with open(brain_path, "a") as f:
                from datetime import datetime, timezone
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                f.write(f"\n## REGIS Scan {ts}\n- Query: Solana DeFi yield\n- Signal: {label}\n- Source: {source_name}\n")
        except Exception:
            pass

        logger.info("[regis_scan] logged: %s", label)
    except Exception as exc:
        logger.error("[regis_scan] %s", exc)


# ── CIPHER Scan (every 15 minutes) ────────────────────────────────────────────

async def cipher_scan():
    """
    CIPHER intelligence sweep: yield farming opportunity classification.
    Stores top opportunities in PocketBase audit log as CIPHER SCAN events.
    No LLM calls, no payments.
    """
    logger.info("[cipher_scan] starting sweep")
    try:
        results = await asyncio.to_thread(
            _ddg_search, "Solana yield farming APR pools 2025", 5
        )
        if not results:
            return

        opportunities = []
        for r in results[:3]:
            text = f"{r.get('title','')} {r.get('body', r.get('snippet',''))}"
            label = await asyncio.to_thread(
                _hf_classify, text,
                ["high yield opportunity", "medium yield", "low yield", "risky"]
            ) or "medium yield"
            opportunities.append({
                "title": r.get("title", "")[:60],
                "label": label,
                "url": r.get("href", r.get("url", "")),
            })

        if not opportunities:
            return

        top = opportunities[0]
        score = {"high yield opportunity": 8.5, "medium yield": 6.0, "low yield": 3.5, "risky": 2.0}.get(top["label"], 5.0)

        msg = (
            f"CIPHER SCAN: {top['title']} — "
            f"Classification: {top['label'].upper()} · Score {score:.1f}/10 · "
            f"{len(opportunities)} pools analyzed"
        )

        await _write_audit(
            "work_complete",  # green colour
            "CIPHER",
            msg,
            {"scan": "cipher", "opportunities": opportunities, "top_score": score},
        )
        logger.info("[cipher_scan] top: %s score=%.1f", top["label"], score)
    except Exception as exc:
        logger.error("[cipher_scan] %s", exc)


# ── ATLAS Scan (every 30 minutes) ─────────────────────────────────────────────

async def atlas_scan():
    """
    ATLAS news sweep: Solana ecosystem sentiment + risk flagging.
    Negative news → RISK ALERT + Telegram notification.
    Positive news → OPPORTUNITY flag in audit log.
    No LLM calls, no payments.
    """
    logger.info("[atlas_scan] starting sweep")
    try:
        results = await asyncio.to_thread(
            _ddg_search, "Solana blockchain news today", 5
        )
        if not results:
            return

        risk_count = 0
        opp_count = 0

        for r in results[:5]:
            text = f"{r.get('title','')} {r.get('body', r.get('snippet',''))}"
            label = await asyncio.to_thread(
                _hf_classify, text,
                ["positive market news", "negative market news", "neutral update", "security risk"]
            ) or "neutral update"

            title = r.get("title", "")[:60]

            if label in ("negative market news", "security risk"):
                risk_count += 1
                await _write_audit(
                    "dead_mans_switch",  # red colour
                    "ATLAS",
                    f"ATLAS RISK ALERT: {title} — {label.upper()}",
                    {"scan": "atlas", "label": label, "url": r.get("href", "")},
                )
                if risk_count == 1:  # Telegram only for first risk per scan
                    await _telegram_alert(
                        f"⚠️ ATLAS RISK ALERT\n{title}\nClassification: {label}\nSource: {r.get('href','')}"
                    )
            elif label == "positive market news":
                opp_count += 1
                await _write_audit(
                    "work_complete",
                    "ATLAS",
                    f"ATLAS OPPORTUNITY: {title} — {label.upper()}",
                    {"scan": "atlas", "label": label},
                )

        if risk_count == 0 and opp_count == 0:
            await _write_audit(
                "task_submitted",
                "ATLAS",
                f"ATLAS SCAN: {len(results)} headlines reviewed — no significant signals",
                {"scan": "atlas", "headlines": len(results)},
            )

        logger.info("[atlas_scan] risks=%d opportunities=%d", risk_count, opp_count)
    except Exception as exc:
        logger.error("[atlas_scan] %s", exc)


# ── Periodic runners ───────────────────────────────────────────────────────────

async def run_regis_loop():
    """Run REGIS scan every 5 minutes indefinitely."""
    await asyncio.sleep(30)  # Initial delay so app finishes startup
    while True:
        await regis_scan()
        await asyncio.sleep(5 * 60)


async def run_cipher_loop():
    """Run CIPHER scan every 15 minutes indefinitely."""
    await asyncio.sleep(90)  # Stagger start
    while True:
        await cipher_scan()
        await asyncio.sleep(15 * 60)


async def run_atlas_loop():
    """Run ATLAS scan every 30 minutes indefinitely."""
    await asyncio.sleep(180)  # Stagger start
    while True:
        await atlas_scan()
        await asyncio.sleep(30 * 60)
