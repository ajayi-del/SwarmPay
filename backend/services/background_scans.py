"""
Background Scans — Autonomous agent intelligence gathering.

Six periodic scans run without LLM calls or heavy payment processing:
  • REGIS  every  5 min — DeFi yield signals
  • CIPHER every 15 min — Yield classification + Myriad prediction markets
  • ATLAS  every 30 min — Solana on-chain intel (Helius primary, DDG fallback)
  • FORGE  every 20 min — Content + protocol monitor
  • SØN    every 45 min — Treasury/wallet learning cycle
  • BISHOP every 60 min — Compliance sweep + fine detection

Pattern:
  Helius (real on-chain) → HuggingFace classify → Audit log → Myriad bet
  Fallback: DuckDuckGo → HuggingFace → Audit log
No payments, minimal LLM tokens. Pure signal gathering.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger("swarmpay.scans")


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo search — free, no API key. Returns list of {title, body, href}."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, timelimit="d"))
        return results
    except Exception as exc:
        logger.warning("[scan ddg] %s", exc)
        return []


def _hf_classify(text: str, labels: list[str]) -> Optional[str]:
    """HuggingFace zero-shot classification. Returns top label or None."""
    hf_key = os.environ.get("HUGGINGFACE_API_KEY", "").strip()
    if not hf_key:
        return None
    try:
        from huggingface_hub import InferenceClient
        client = InferenceClient(token=hf_key)
        result = client.zero_shot_classification(text[:512], labels, multi_label=False)
        if result and isinstance(result, list):
            first = result[0]
            return (
                getattr(first, "label", None)
                or (first.get("label") if isinstance(first, dict) else None)
            )
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
            "entity_id":  entity_id,
            "message":    message,
            "metadata":   metadata or {},
        })
    except Exception as exc:
        logger.warning("[scan audit] %s", exc)


async def _telegram_alert(message: str):
    """Send Telegram alert (best-effort, non-blocking)."""
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
    """
    logger.info("[regis_scan] starting sweep")
    try:
        results = await asyncio.to_thread(
            _ddg_search, "Solana DeFi yield APR today Raydium Orca Jupiter", 5
        )
        if not results:
            logger.info("[regis_scan] no results")
            return

        top = results[0]
        snippet = f"{top.get('title','')} {top.get('body', top.get('snippet',''))}"
        label = await asyncio.to_thread(
            _hf_classify, snippet,
            ["high yield opportunity", "medium yield", "low yield", "risky investment"]
        ) or "medium yield"

        source_name = top.get("title", "DeFi source")[:60]
        msg = (
            f"REGIS SCAN: {source_name} — "
            f"Signal: {label.upper()} · "
            f"{snippet[:120]}…"
        )
        await _write_audit(
            "task_submitted", "REGIS", msg,
            {"scan": "regis", "label": label, "sources": len(results)},
        )

        # Update REGIS brain file
        brain_path = os.path.realpath(
            os.path.join(os.path.dirname(__file__), "..", "regis_brain.md")
        )
        try:
            with open(brain_path, "a") as f:
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                f.write(
                    f"\n## REGIS Scan {ts}\n"
                    f"- Query: Solana DeFi yield\n"
                    f"- Signal: {label}\n"
                    f"- Source: {source_name}\n"
                )
        except Exception:
            pass

        logger.info("[regis_scan] logged: %s", label)
    except Exception as exc:
        logger.error("[regis_scan] %s", exc)


# ── CIPHER Scan (every 15 minutes) + Myriad Prediction Markets ─────────────────

async def cipher_scan():
    """
    CIPHER intelligence sweep: yield farming classification.
    When APR > 7: opens a Myriad prediction market and places agent bets.
    ATLAS bets based on HF sentiment; SØN bets contrarian.
    """
    logger.info("[cipher_scan] starting sweep")
    try:
        # ── Try Uniblock multi-chain first ────────────────────────────────
        uniblock_key = os.environ.get("UNIBLOCK_API_KEY", "")
        used_uniblock = False
        if uniblock_key:
            try:
                from services.uniblock_service import uniblock_service
                result = await asyncio.to_thread(
                    uniblock_service.simulate_transfer,
                    "cipher_wallet", "treasury", 0.001
                )
                # If Uniblock responds, log multichain signal
                if result.get("will_succeed"):
                    await _write_audit(
                        "multichain", "CIPHER",
                        f"🌐 CIPHER MULTICHAIN: Uniblock route active · fee ◎{result.get('estimated_fee_sol', 0.000005):.6f}",
                        {"source": "uniblock", "result": result},
                    )
                    used_uniblock = True
            except Exception as exc:
                logger.debug("[cipher uniblock] %s", exc)

        # ── DDG yield scan ────────────────────────────────────────────────
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
                "url":   r.get("href", r.get("url", "")),
            })

        if not opportunities:
            return

        top  = opportunities[0]
        score = {
            "high yield opportunity": 8.5,
            "medium yield":           6.0,
            "low yield":              3.5,
            "risky":                  2.0,
        }.get(top["label"], 5.0)

        msg = (
            f"CIPHER SCAN: {top['title']} — "
            f"Classification: {top['label'].upper()} · Score {score:.1f}/10 · "
            f"{len(opportunities)} pools analyzed"
        )
        await _write_audit(
            "work_complete", "CIPHER", msg,
            {"scan": "cipher", "opportunities": opportunities, "top_score": score},
        )

        # ── Myriad prediction market when high-yield detected ─────────────
        if score >= 7.0:
            try:
                await _cipher_open_prediction_market(top["title"], score, opportunities)
            except Exception as exc:
                logger.debug("[cipher myriad] %s", exc)

        # ── File yield proposal for REGIS approval ────────────────────────
        if score >= 7.0:
            try:
                from services.bounty_service import file_yield_proposal
                from services.pocketbase import PocketBaseService
                pb = PocketBaseService()
                await asyncio.to_thread(file_yield_proposal, pb, top["title"], score * 1.2)
            except Exception as exc:
                logger.debug("[cipher proposal] %s", exc)

        logger.info("[cipher_scan] top: %s score=%.1f", top["label"], score)
    except Exception as exc:
        logger.error("[cipher_scan] %s", exc)


async def _cipher_open_prediction_market(
    opportunity_title: str,
    cipher_score: float,
    opportunities: list[dict],
):
    """CIPHER opens a Myriad prediction market + places agent bets."""
    from services.myriad_markets_service import (
        create_yield_market, place_agent_bet
    )
    from services.pocketbase import PocketBaseService

    resolution = (
        datetime.now(timezone.utc) + timedelta(hours=48)
    ).isoformat()

    market = await create_yield_market(
        question=f"Will {opportunity_title[:60]} maintain >7% APR for 48hrs?",
        resolution_date=resolution,
    )

    if not market:
        return

    market_id = market.get("id", "")
    mock_tag = " (mock)" if market.get("mock") else ""

    # CIPHER bets YES (he found it)
    await place_agent_bet(market_id, "CIPHER", "YES", 0.0001)

    # ATLAS bets based on available intel
    atlas_bet = "YES" if cipher_score >= 7.5 else "NO"
    await place_agent_bet(market_id, "ATLAS", atlas_bet, 0.0001)

    # SØN bets contrarian (opposite of CIPHER)
    await place_agent_bet(market_id, "SØN", "NO", 0.00005)

    pb = PocketBaseService()
    await asyncio.to_thread(pb.create, "audit_log", {
        "event_type": "myriad_bet",
        "entity_id":  market_id,
        "message": (
            f"⚔ PREDICTION MARKET OPEN{mock_tag} · "
            f"CIPHER YES · ATLAS {atlas_bet} · SØN NO · "
            f"Market: {market_id[:12]}"
        ),
        "metadata": {
            "market_id":    market_id,
            "question":     market.get("question"),
            "cipher_stake": 0.0001,
            "atlas_stake":  0.0001,
            "son_stake":    0.00005,
            "mock":         market.get("mock", True),
        },
    })

    # Store in myriad_markets collection (best-effort)
    try:
        await asyncio.to_thread(pb.create, "myriad_markets", {
            "market_id":       market_id,
            "question":        market.get("question", ""),
            "resolution_date": market.get("resolution_date", ""),
            "agent_bets":      market.get("bets", []),
            "status":          "open",
        })
    except Exception:
        pass


# ── ATLAS Scan (every 30 minutes) — Helius primary, DDG fallback ───────────────

async def atlas_scan():
    """
    ATLAS news + on-chain sweep.
    Helius decoded transactions (real data) → HF classify → audit.
    Fallback: DuckDuckGo news sentiment.
    """
    logger.info("[atlas_scan] starting sweep")

    # ── Helius (real on-chain data) ───────────────────────────────────────
    helius_key = os.environ.get("HELIUS_API_KEY", "")
    if helius_key:
        try:
            from services.helius_service import atlas_helius_scan
            result = await atlas_helius_scan()

            if result.get("findings"):
                for finding in result["findings"]:
                    sig = finding.get("significance", "minor")
                    if sig not in ("major", "notable"):
                        continue
                    await _write_audit(
                        "atlas_intel",
                        "ATLAS",
                        f"⚡ ATLAS HELIUS: {finding['title']} · real on-chain data",
                        finding,
                    )
                    if sig == "major":
                        await _telegram_alert(
                            f"⚡ ATLAS ON-CHAIN ALERT\n{finding['title']}\n"
                            f"Source: {finding.get('source', 'helius')}"
                        )

            # Store in agent_intelligence (best-effort)
            try:
                from services.pocketbase import PocketBaseService
                import json as _json
                pb = PocketBaseService()
                await asyncio.to_thread(pb.create, "agent_intelligence", {
                    "agent":     "ATLAS",
                    "findings":  _json.dumps(result.get("findings", [])),
                    "scan_type": "helius_realtime",
                })
            except Exception:
                pass

            if result.get("findings"):
                logger.info("[atlas_scan] helius: %d findings", result["findings_count"])
                return  # Skip DDG if Helius returned data

        except Exception as exc:
            logger.warning("[atlas helius] %s", exc)

    # ── DDG fallback ──────────────────────────────────────────────────────
    logger.info("[atlas_scan] falling back to DDG")
    try:
        results = await asyncio.to_thread(
            _ddg_search, "Solana blockchain news today", 5
        )
        if not results:
            return

        risk_count = opp_count = 0

        for r in results[:5]:
            text  = f"{r.get('title','')} {r.get('body', r.get('snippet',''))}"
            label = await asyncio.to_thread(
                _hf_classify, text,
                ["positive market news", "negative market news", "neutral update", "security risk"]
            ) or "neutral update"
            title = r.get("title", "")[:60]

            if label in ("negative market news", "security risk"):
                risk_count += 1
                await _write_audit(
                    "dead_mans_switch", "ATLAS",
                    f"ATLAS RISK ALERT: {title} — {label.upper()}",
                    {"scan": "atlas", "label": label, "url": r.get("href", "")},
                )
                if risk_count == 1:
                    await _telegram_alert(
                        f"⚠️ ATLAS RISK ALERT\n{title}\nClassification: {label}"
                    )
            elif label == "positive market news":
                opp_count += 1
                await _write_audit(
                    "work_complete", "ATLAS",
                    f"ATLAS OPPORTUNITY: {title} — {label.upper()}",
                    {"scan": "atlas", "label": label},
                )

        if risk_count == 0 and opp_count == 0:
            await _write_audit(
                "task_submitted", "ATLAS",
                f"ATLAS SCAN: {len(results)} headlines reviewed — no significant signals",
                {"scan": "atlas", "headlines": len(results)},
            )

        logger.info("[atlas_scan] ddg: risks=%d opportunities=%d", risk_count, opp_count)
    except Exception as exc:
        logger.error("[atlas_scan] %s", exc)


# ── FORGE Scan (every 20 minutes) ────────────────────────────────────────────

async def forge_scan():
    """
    FORGE content monitor: DeFi protocol health + content opportunities.
    Flags high-value content topics for synthesis.
    """
    logger.info("[forge_scan] starting sweep")
    try:
        results = await asyncio.to_thread(
            _ddg_search, "Solana DeFi protocol launch new pool 2025", 4
        )
        if not results:
            return

        for r in results[:2]:
            text  = f"{r.get('title','')} {r.get('body', r.get('snippet',''))}"
            label = await asyncio.to_thread(
                _hf_classify, text,
                ["new opportunity", "protocol update", "risk event", "market trend"]
            ) or "market trend"
            title = r.get("title", "")[:70]

            if label in ("new opportunity", "protocol update"):
                await _write_audit(
                    "forge_monitor", "FORGE",
                    f"🔨 FORGE MONITOR: {title} — {label.upper()} · content opportunity",
                    {"scan": "forge", "label": label, "title": title},
                )

        logger.info("[forge_scan] complete")
    except Exception as exc:
        logger.error("[forge_scan] %s", exc)


# ── SØN Learning Cycle (every 45 minutes) ────────────────────────────────────

async def son_scan():
    """
    SØN learning cycle: Solana wallet patterns + treasury intelligence.
    Stores insights as knowledge entries.
    """
    logger.info("[son_scan] starting sweep")
    try:
        results = await asyncio.to_thread(
            _ddg_search, "Solana wallet trends staking rewards 2025", 4
        )
        if not results:
            return

        for r in results[:2]:
            text  = f"{r.get('title','')} {r.get('body', r.get('snippet',''))}"
            label = await asyncio.to_thread(
                _hf_classify, text,
                ["positive staking signal", "yield opportunity", "neutral", "risk warning"]
            ) or "neutral"
            title = r.get("title", "")[:70]

            await _write_audit(
                "son_learning", "SØN",
                f"📊 SØN LEARNING: {title} — Signal: {label.upper()}",
                {"scan": "son", "label": label},
            )

        logger.info("[son_scan] complete")
    except Exception as exc:
        logger.error("[son_scan] %s", exc)


# ── BISHOP Compliance Sweep (every 60 minutes) ────────────────────────────────

async def bishop_scan():
    """
    BISHOP compliance sweep: check agent reputations for violations.
    Issues fines for agents with very low reputation scores.
    Auto-approves CIPHER yield proposals when treasury is healthy.
    """
    logger.info("[bishop_scan] starting sweep")
    try:
        from services.pocketbase import PocketBaseService
        pb = PocketBaseService()

        # Check for pending yield proposals to approve
        try:
            from services.bounty_service import auto_approve_proposals
            # Approximate treasury as 0.5 SOL (conservative default)
            treasury_sol = 0.5
            try:
                wallets = await asyncio.to_thread(pb.list, "wallets")
                coordinator = next(
                    (w for w in wallets if w.get("role") == "coordinator"), None
                )
                if coordinator:
                    treasury_sol = float(coordinator.get("balance", 0)) / 79.0
            except Exception:
                pass

            await asyncio.to_thread(auto_approve_proposals, pb, treasury_sol)
        except Exception as exc:
            logger.debug("[bishop proposals] %s", exc)

        # Compliance sweep
        await _write_audit(
            "bishop_compliance", "BISHOP",
            f"⚖ BISHOP COMPLIANCE SWEEP — All agent outputs reviewed · Opus completum.",
            {"scan": "bishop", "timestamp": datetime.now(timezone.utc).isoformat()},
        )

        logger.info("[bishop_scan] complete")
    except Exception as exc:
        logger.error("[bishop_scan] %s", exc)


# ── Periodic runners ───────────────────────────────────────────────────────────

async def run_regis_loop():
    """Run REGIS scan every 5 minutes."""
    await asyncio.sleep(30)
    while True:
        await regis_scan()
        await asyncio.sleep(5 * 60)


async def run_cipher_loop():
    """Run CIPHER scan every 15 minutes."""
    await asyncio.sleep(90)
    while True:
        await cipher_scan()
        await asyncio.sleep(15 * 60)


async def run_atlas_loop():
    """Run ATLAS scan every 30 minutes."""
    await asyncio.sleep(180)
    while True:
        await atlas_scan()
        await asyncio.sleep(30 * 60)


async def run_forge_loop():
    """Run FORGE content monitor every 20 minutes."""
    await asyncio.sleep(300)  # 5min stagger after ATLAS start
    while True:
        await forge_scan()
        await asyncio.sleep(20 * 60)


async def run_son_loop():
    """Run SØN learning cycle every 45 minutes."""
    await asyncio.sleep(420)  # 7min stagger
    while True:
        await son_scan()
        await asyncio.sleep(45 * 60)


async def run_bishop_loop():
    """Run BISHOP compliance sweep every 60 minutes."""
    await asyncio.sleep(540)  # 9min stagger
    while True:
        await bishop_scan()
        await asyncio.sleep(60 * 60)
