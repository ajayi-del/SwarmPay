"""
REGIS Telegram Bot — SwarmPay field commander interface.

Philosophy: Telegram speaks only on signal events.
Every message is actionable or confirmatory. Silence during routine operations.

Notification Gate:
  Signal events  → always send (payment_blocked, task_complete, dead_mans_switch,
                   x402_confirmed, challenge_result, punish_applied)
  Routine events → always suppressed (agent_spawned, wallet_created, peer_payment,
                   payment_signed, task_submitted, backend_started)

Commands:
  /start          — welcome
  /help           — command list
  /deploy <task> budget:<amount>  — launch swarm, fire & forget, one completion msg
  /status         — latest task summary
  /probe <q>      — ask REGIS anything
  /audit          — run governance audit
  /punish <type>  — slash | demote | report
  /fund <amount>  — MoonPay fiat → SOL link
  /treasury       — REGIS brain summary
  /economy        — swarm efficiency stats
  /logs [n]       — recent audit events
  /agents         — agent roster + rep + status
  /reputations    — live rep scores
  /lock <AGENT>   — suspend agent
  /unlock <AGENT> — reactivate agent
  /locked         — list suspended agents
  /challenge <N>  — challenge REGIS for coordinator
  /solana         — Solana devnet wallets
  /ows            — OWS wallet permissions
  /moonpay [amt]  — alias for /fund
  /model          — current model routing
  /dryrun         — switch to dry run mode
  /live           — switch to live mode
  /brain          — recent REGIS memory
  Any plain text  — REGIS in-character probe
"""

import asyncio
import json
import logging
import os
import time
import traceback
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("swarmpay.telegram")

TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))
BACKEND_URL     = os.environ.get("BACKEND_URL", "http://localhost:8000")
MOONPAY_API_KEY = os.environ.get("MOONPAY_API_KEY", "")

_TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ── Notification Gate ──────────────────────────────────────────────────────────

class _NotificationGate:
    """
    Filters backend events to Telegram.
    Only signal events are forwarded. Cooldown prevents spam per event type.
    """
    SIGNAL_EVENTS = {
        "payment_blocked",
        "task_complete",
        "dead_mans_switch",
        "x402_confirmed",
        "challenge_result",
        "moonpay_received",
        "punish_applied",
        "task_failed",
        "treasury_low",
        "pending_overthrow",
    }
    COOLDOWN_SECONDS = 30

    def __init__(self):
        self._cooldowns: Dict[str, float] = {}

    def should_notify(self, event_type: str) -> bool:
        if event_type not in self.SIGNAL_EVENTS:
            return False
        now = time.time()
        last = self._cooldowns.get(event_type, 0)
        if now - last < self.COOLDOWN_SECONDS:
            return False
        self._cooldowns[event_type] = now
        return True


_gate = _NotificationGate()


async def notify_event(event_type: str, message: str) -> None:
    """
    Called by backend services to fire a Telegram notification.
    Passes through NotificationGate — only signal events reach Telegram.
    Never raises.
    """
    if not _gate.should_notify(event_type):
        return
    await send(ALLOWED_CHAT_ID, message)


# ── HTTP helpers ───────────────────────────────────────────────────────────────

async def _tg(method: str, **kwargs) -> dict:
    """Call a Telegram Bot API method. Never raises."""
    if not TELEGRAM_TOKEN:
        return {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(f"{_TG_API}/{method}", json=kwargs)
            return r.json() if r.is_success else {}
    except Exception as exc:
        logger.debug("[tg] %s failed: %s", method, exc)
        return {}


async def _backend(path: str, method: str = "GET", body: dict = None) -> dict:
    """Call the SwarmPay backend. Never raises — returns {} on failure."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            if method == "POST":
                r = await c.post(f"{BACKEND_URL}{path}", json=body or {})
            else:
                r = await c.get(f"{BACKEND_URL}{path}")
            return r.json() if r.is_success else {}
    except Exception as exc:
        logger.debug("[backend] %s %s failed: %s", method, path, exc)
        return {}


async def _pb(path: str) -> dict:
    """Query PocketBase directly (separate from FastAPI backend)."""
    pb_url = os.environ.get("POCKETBASE_URL", "http://localhost:8090")
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get(f"{pb_url}{path}")
            return r.json() if r.is_success else {}
    except Exception as exc:
        logger.debug("[pb] %s failed: %s", path, exc)
        return {}


async def send(chat_id: int, text: str, parse_mode: str = "") -> None:
    """Send a Telegram message, auto-split if > 4000 chars. Never raises."""
    if not TELEGRAM_TOKEN or not chat_id:
        return
    max_len = 4000
    chunks = [text[i:i + max_len] for i in range(0, max(len(text), 1), max_len)]
    for chunk in chunks:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": chunk}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        await _tg("sendMessage", **payload)


# ── Command handlers ───────────────────────────────────────────────────────────

async def cmd_start(chat_id: int):
    await send(chat_id,
        "REGIS SOVEREIGN BRAIN — Command Terminal\n"
        "SwarmPay Agent Economy v2.0\n\n"
        "I sign payments, block violations, punish misconduct,\n"
        "and remember everything.\n\n"
        "Type /help for commands."
    )


async def cmd_help(chat_id: int):
    await send(chat_id,
        "REGIS Command Registry\n"
        "──────────────────────\n"
        "/deploy <task> budget:<amt>  — launch swarm\n"
        "/status                      — latest task\n"
        "/probe <question>            — consult REGIS\n"
        "/audit                       — governance audit\n"
        "/punish slash|demote|report  — punish REGIS\n"
        "/fund <usd_amount>           — MoonPay onramp\n"
        "/treasury                    — REGIS brain summary\n"
        "/economy                     — swarm efficiency\n"
        "/logs [n]                    — recent audit events\n"
        "/agents                      — agent roster + rep\n"
        "──── Agent Control ────\n"
        "/lock <AGENT>                — suspend agent\n"
        "/unlock <AGENT>              — reactivate agent\n"
        "/locked                      — suspended agents\n"
        "/challenge <AGENT>           — challenge REGIS\n"
        "──── Infrastructure ───\n"
        "/reputations                 — live rep scores\n"
        "/solana                      — Solana wallets\n"
        "/ows                         — OWS permissions\n"
        "/moonpay [amt]               — onramp link\n"
        "/brain                       — recent memory\n"
        "/model                       — model routing\n"
        "/dryrun  /live               — mode toggle\n"
        "──── Governance ───────\n"
        "/approve <AGENT>             — approve succession\n"
        "/veto <AGENT>                — veto overthrow\n"
        "\nOr send any text to speak with REGIS."
    )


async def cmd_deploy(chat_id: int, args: str):
    """
    /deploy <task description> budget:<amount>
    Fire and forget — one completion signal when done.
    """
    # Parse description and budget
    description = args.strip()
    budget = 15.0
    if "budget:" in description.lower():
        parts = description.lower().split("budget:")
        try:
            budget = float(parts[-1].strip().split()[0])
        except ValueError:
            pass
        description = description[:description.lower().rfind("budget:")].strip()

    if not description:
        await send(chat_id, "Usage: /deploy Research DeFi trends budget:10")
        return

    await send(chat_id,
        f"⚔ SWARM DEPLOYING\n"
        f"─────────────────\n"
        f"Task: {description[:80]}\n"
        f"Budget: {budget} USDC\n"
        f"Agents selected autonomously by REGIS.\n"
        f"Executing silently — you will be notified on completion."
    )

    try:
        r1 = await _backend("/task/submit", "POST", {"description": description, "budget": budget})
        task_id = r1.get("task_id")
        if not task_id:
            await send(chat_id, f"Submit failed: no task_id returned.")
            return

        r2 = await _backend("/task/decompose", "POST", {"task_id": task_id})
        if not r2.get("sub_tasks"):
            await send(chat_id, f"Decompose failed. Task ID: {task_id}")
            return

        # Fire execute — don't await the completion
        asyncio.create_task(_backend("/task/execute", "POST", {"task_id": task_id}))

    except Exception as exc:
        await send(chat_id, f"Deploy error: {exc}")


async def cmd_status(chat_id: int, args: str = ""):
    """Show latest (or specific) task status."""
    try:
        task_id = args.strip() if args.strip() else None

        if not task_id:
            r = await _pb("/api/collections/tasks/records?sort=-created&perPage=1")
            items = r.get("items", [])
            if not items:
                await send(chat_id, "No tasks found. Use /deploy <task> to start one.")
                return
            task_id = items[0].get("id")

        full = await _backend(f"/task/{task_id}/status")
        t    = full.get("task", {})
        subs = full.get("sub_tasks", [])

        lines = [
            "SWARM STATUS",
            f"Task: {str(t.get('description',''))[:60]}",
            f"─────────────────",
        ]
        status_icons = {
            "paid": "✓", "complete": "✓", "working": "⟳",
            "spawned": "◎", "blocked": "✗", "failed": "✗",
            "timed_out": "⏱",
        }
        total_paid = 0.0
        for st in subs:
            agent  = st.get("agent_id", "?")
            status = st.get("status", "?")
            icon   = status_icons.get(status, "?")
            bud    = float(st.get("budget_allocated", 0))
            total_paid += bud if status == "paid" else 0
            lines.append(f"  {agent:8} {icon} {status.upper():10}  {bud:.3f} USDC")

        lines += [
            f"─────────────────",
            f"Status:  {t.get('status','?').upper()}",
            f"Budget:  {t.get('total_budget', 0)} USDC",
        ]
        await send(chat_id, "\n".join(lines))
    except Exception as exc:
        await send(chat_id, f"Status query failed: {exc}")


async def cmd_probe(chat_id: int, question: str):
    if not question.strip():
        await send(chat_id, "Usage: /probe <your question>")
        return
    try:
        r = await _backend("/regis/probe", "POST", {"question": question})
        answer = r.get("answer") or r.get("response") or "No answer."
        await send(chat_id, f"👑 REGIS:\n{answer}")
    except Exception as exc:
        await send(chat_id, f"Probe failed: {exc}")


async def cmd_audit(chat_id: int):
    await send(chat_id, "Running REGIS governance audit…")
    try:
        r = await _backend("/regis/audit", "POST", {})
        score   = r.get("score", 0)
        verdict = r.get("verdict", "?")
        delta   = r.get("rep_delta", 0)
        reason  = r.get("reason", "")
        icon    = "✅" if verdict == "PASSED" else ("⚠️" if verdict == "MARGINAL" else "❌")
        await send(chat_id,
            f"⚖️ AUDIT COMPLETE\n"
            f"─────────────────\n"
            f"{icon} Score:   {score}/100 — {verdict}\n"
            f"Rep Δ:   {'+' if delta >= 0 else ''}{delta:.1f}★\n"
            f"Finding: {reason[:200]}"
        )
    except Exception as exc:
        await send(chat_id, f"Audit failed: {exc}")


async def cmd_punish(chat_id: int, args: str):
    """
    /punish slash|demote|report
    """
    ptype_map = {
        "slash": "slash_treasury",
        "demote": "demote_reputation",
        "report": "governance_report",
    }
    ptype = ptype_map.get(args.strip().lower(), "")
    if not ptype:
        await send(chat_id, "Usage: /punish slash | demote | report")
        return
    try:
        # Get coordinator wallet for slash
        r_w = await _pb("/api/collections/wallets/records?filter=role%3D'coordinator'&sort=-created&perPage=1")
        wallets = r_w.get("items", [])
        wallet_id = wallets[0].get("id") if wallets else None

        payload = {"punishment_type": ptype}
        if wallet_id and ptype == "slash_treasury":
            payload["coordinator_wallet_id"] = wallet_id

        r = await _backend("/regis/punish", "POST", payload)
        regis_response = r.get("response", "REGIS acknowledged.")

        icons = {
            "slash_treasury":    "⚔️ TREASURY SLASHED",
            "demote_reputation": "📉 REGIS DEMOTED",
            "governance_report": "📜 REPORT ORDERED",
        }
        await send(chat_id,
            f"{icons.get(ptype, '🔨 PUNISHMENT')}\n"
            f"────────────────────────────\n"
            f"REGIS: \"{regis_response[:300]}\""
        )
    except Exception as exc:
        await send(chat_id, f"Punish failed: {exc}")


async def cmd_fund(chat_id: int, args: str):
    """
    /fund <amount_usd>
    Generate MoonPay link to fund REGIS treasury.
    """
    try:
        amount = float(args.strip()) if args.strip() else 20.0
    except ValueError:
        amount = 20.0

    try:
        r = await _pb("/api/collections/wallets/records?filter=role%3D'coordinator'&sort=-created&perPage=1")
        wallets = r.get("items", [])
        sol_address = wallets[0].get("sol_address", "") if wallets else ""

        if not sol_address:
            await send(chat_id,
                "No active REGIS treasury wallet found.\n"
                "Launch a task first with /deploy."
            )
            return

        # Build MoonPay URL
        if MOONPAY_API_KEY:
            base    = "https://buy.moonpay.com"
            api_key = MOONPAY_API_KEY
            mode    = "LIVE"
        else:
            base    = "https://buy-sandbox.moonpay.com"
            api_key = "pk_test_key"
            mode    = "SANDBOX"

        params = {
            "apiKey":               api_key,
            "currencyCode":         "usdc_sol",
            "walletAddress":        sol_address,
            "baseCurrencyCode":     "usd",
            "baseCurrencyAmount":   str(amount),
            "colorCode":            "#a78bfa",
            "redirectURL":          "https://swarm.pay/funded",
            "externalTransactionId": f"swarm_{sol_address[:8]}",
        }
        url = f"{base}?{urlencode(params)}"

        await send(chat_id,
            f"💰 FUND REGIS TREASURY [{mode}]\n"
            f"─────────────────────────────\n"
            f"Amount:  ${amount:.2f} USD → USDC\n"
            f"Wallet:  {sol_address[:24]}…\n"
            f"Network: Solana devnet\n\n"
            f"Complete the purchase in your browser.\n"
            f"Treasury will reflect funds on receipt.\n\n"
            f"{url}"
        )
    except Exception as exc:
        await send(chat_id, f"Fund link failed: {exc}")


async def cmd_treasury(chat_id: int):
    """Parse REGIS brain + wallet to show treasury summary."""
    try:
        r = await _backend("/regis/brain")
        content = r.get("content", "")
        last_updated = r.get("last_updated", "—")

        # Count entries
        lines = [l for l in content.splitlines() if l.startswith("[")]
        task_lines   = [l for l in lines if "TASK_COMPLETE" in l]
        probe_lines  = [l for l in lines if "PROBE_Q" in l]
        audit_lines  = [l for l in lines if "AUDIT" in l]
        punish_lines = [l for l in lines if "PUNISHMENT" in l]

        # Get coordinator wallet
        r_w = await _pb("/api/collections/wallets/records?filter=role%3D'coordinator'&sort=-created&perPage=1")
        wallets = r_w.get("items", [])
        wallet = wallets[0] if wallets else {}
        balance = float(wallet.get("balance", 0))
        cap     = float(wallet.get("budget_cap", 0))
        sol_addr = wallet.get("sol_address", "—")

        await send(chat_id,
            f"👑 REGIS TREASURY\n"
            f"─────────────────\n"
            f"Balance:   {balance:.4f} USDC / {cap:.4f} cap\n"
            f"SOL:       {sol_addr[:24] if sol_addr != '—' else '—'}…\n"
            f"Tasks run: {len(task_lines)}\n"
            f"Probes:    {len(probe_lines)}\n"
            f"Audits:    {len(audit_lines)}\n"
            f"Punishments: {len(punish_lines)}\n"
            f"Last entry: {last_updated or '—'}\n\n"
            f"Recent:\n" + "\n".join(f"  {l[:100]}" for l in lines[-3:])
        )
    except Exception as exc:
        await send(chat_id, f"Treasury query failed: {exc}")


async def cmd_economy(chat_id: int):
    """GET /swarm/stats → economy summary."""
    try:
        r = await _backend("/swarm/stats")
        signed  = r.get("total_signed", 0)
        blocked = r.get("total_blocked", 0)
        total   = signed + blocked
        pct     = round(signed / total * 100) if total else 0
        peers   = r.get("peer_count", 0)
        health  = r.get("health_score", 0)
        await send(chat_id,
            f"📊 SWARM ECONOMY\n"
            f"────────────────\n"
            f"Health score:  {health}/100\n"
            f"Tasks run:     {r.get('total_tasks', 0)}\n"
            f"Payments out:  {signed} signed · {blocked} blocked\n"
            f"Efficiency:    {pct}%\n"
            f"Peer txs:      {peers}\n"
            f"USDC paid:     {r.get('eth_processed', 0):.4f}\n"
            f"USDC held:     {r.get('eth_held', 0):.4f}\n"
            f"Avg rep:       {r.get('avg_reputation', 0):.2f}★"
        )
    except Exception as exc:
        await send(chat_id, f"Economy query failed: {exc}")


async def cmd_logs(chat_id: int, args: str):
    """GET /audit?limit=n → event feed."""
    try:
        n = int(args.strip()) if args.strip().isdigit() else 5
        n = min(n, 20)
        r = await _backend(f"/audit?limit={n}")
        logs = r.get("logs", [])
        if not logs:
            await send(chat_id, "No audit events yet.")
            return
        lines = [f"AUDIT LOG (last {len(logs)})\n────────────────────"]
        for ev in reversed(logs):
            ts      = str(ev.get("created", ""))[:16].replace("T", " ")
            etype   = ev.get("event_type", "?")[:18]
            message = ev.get("message", "")[:60]
            icon    = {"payment_signed": "✓", "payment_blocked": "✗",
                       "task_complete": "✅", "dead_mans_switch": "⏱",
                       "work_complete": "◎", "agent_spawned": "+"}.get(
                           ev.get("event_type", ""), "·")
            lines.append(f"[{ts}] {icon} {etype}\n  {message}")
        await send(chat_id, "\n".join(lines))
    except Exception as exc:
        await send(chat_id, f"Logs query failed: {exc}")


async def cmd_agents(chat_id: int):
    """Show all agents with status from latest task."""
    try:
        r = await _pb("/api/collections/tasks/records?sort=-created&perPage=1")
        items = r.get("items", [])
        if not items:
            await send(chat_id, "No tasks found.")
            return
        task_id = items[0].get("id")
        full = await _backend(f"/task/{task_id}/status")
        subs = full.get("sub_tasks", [])

        from services.pocketbase import PocketBaseService
        pb = PocketBaseService()
        reps = pb.get_all_reputations()

        lines = ["AGENT ROSTER\n────────────"]

        agent_data = [
            ("REGIS",  "🇬🇧", "Coordinator", "★★★★★"),
            ("ATLAS",  "🇩🇪", "Researcher",  ""),
            ("CIPHER", "🇯🇵", "Analyst",     ""),
            ("FORGE",  "🇳🇬", "Synthesizer", ""),
            ("BISHOP", "🇻🇦", "Compliance",  ""),
            ("SØN",    "🇸🇪", "Heir",        ""),
        ]

        sub_map = {st["agent_id"]: st for st in subs}
        status_icons = {"paid": "✓", "complete": "✓", "working": "⟳",
                        "blocked": "✗", "failed": "✗", "spawned": "◎", "timed_out": "⏱"}

        for name, flag, role, fixed_stars in agent_data:
            rep = reps.get(name, 3.0) if name != "REGIS" else 5.0
            stars = fixed_stars or "●" * int(rep) + "○" * (5 - int(rep))
            sub   = sub_map.get(name)
            if sub:
                status = sub.get("status", "?")
                icon   = status_icons.get(status, "?")
                bud    = float(sub.get("budget_allocated", 0))
                lines.append(f"{flag} {name:8} [{role[:10]}]  {stars}  {icon} {status.upper()}  {bud:.3f} USDC")
            else:
                lines.append(f"{flag} {name:8} [{role[:10]}]  {stars}  ◌ idle")

        await send(chat_id, "\n".join(lines))
    except Exception as exc:
        await send(chat_id, f"Agents query failed: {exc}")


async def cmd_balance(chat_id: int):
    try:
        r = await _pb("/api/collections/wallets/records?filter=role%3D'coordinator'&sort=-created&perPage=3")
        wallets = r.get("items", [])
        if not wallets:
            await send(chat_id, "No active treasury found. Launch a task first.")
            return
        w = wallets[0]
        rate_data = await _backend("/regis/meteora")
        rate = rate_data.get("rate")
        sol_addr = w.get("sol_address", "—")
        balance  = float(w.get("balance", 0))
        budget   = float(w.get("budget_cap", 0))
        msg = (
            f"TREASURY STATUS\n"
            f"───────────────\n"
            f"Coordinator: {w.get('name', '?')}\n"
            f"Budget cap:  {budget:.2f} USDC\n"
            f"Balance:     {balance:.4f}\n"
            f"SOL address: {sol_addr[:20]}…\n"
        )
        if rate:
            msg += f"SOL/USDC:    {rate} ({rate_data.get('source','')[:20]})\n"
        await send(chat_id, msg)
    except Exception as exc:
        await send(chat_id, f"Treasury query failed: {exc}")


async def cmd_brain(chat_id: int):
    try:
        r = await _backend("/regis/brain")
        content = r.get("content", "")
        lines = [l for l in content.splitlines() if l.startswith("[")]
        if not lines:
            await send(chat_id, "Brain is empty. No tasks completed yet.")
            return
        out = ["REGIS BRAIN (last 10)\n─────────────────────"]
        for l in lines[-10:]:
            out.append(l[:120])
        await send(chat_id, "\n".join(out))
    except Exception as exc:
        await send(chat_id, f"Brain query failed: {exc}")


async def cmd_reputations(chat_id: int):
    try:
        r = await _pb("/api/collections/agent_reputation/records?perPage=10")
        recs = r.get("items", [])
        if not recs:
            await send(chat_id, "No reputation records found.")
            return
        lines = ["AGENT REPUTATIONS\n─────────────────"]

        from services.quality_service import get_avg_quality, qualifies_for_challenge
        from services.agent_lock_service import is_locked

        def _stars(rep: float) -> str:
            full  = int(rep)
            half  = 1 if rep - full >= 0.5 else 0
            empty = 5 - full - half
            return "●" * full + "◐" * half + "○" * empty

        for rec in sorted(recs, key=lambda x: -float(x.get("current_reputation", 0))):
            rep  = float(rec.get("current_reputation", 0))
            name = rec.get("agent_id", "?")
            avg_q = get_avg_quality(name)
            lock_icon      = " 🔒" if is_locked(name) else ""
            challenge_icon = " ⚔" if qualifies_for_challenge(name, rep) else ""
            lines.append(f"{name:8} {_stars(rep)} {rep:.2f}★  q:{avg_q:.1f}/10{lock_icon}{challenge_icon}")
        lines += ["\n⚔ = eligible to challenge REGIS", "🔒 = locked (use /unlock NAME)"]
        await send(chat_id, "\n".join(lines))
    except Exception as exc:
        await send(chat_id, f"Reputation query failed: {exc}")


async def cmd_tasks_list(chat_id: int):
    try:
        r = await _pb("/api/collections/tasks/records?sort=-created&perPage=5")
        tasks = r.get("items", [])
        if not tasks:
            await send(chat_id, "No tasks found.")
            return
        lines = ["RECENT TASKS\n────────────"]
        for t in tasks:
            desc   = str(t.get("description", ""))[:45]
            status = str(t.get("status", "?")).upper()
            lines.append(f"{t.get('id','')} · {status}\n  {desc}")
        await send(chat_id, "\n".join(lines))
    except Exception as exc:
        await send(chat_id, f"Task list failed: {exc}")


async def cmd_solana(chat_id: int):
    try:
        r = await _pb("/api/collections/wallets/records?sort=-created&perPage=10")
        wallets = r.get("items", [])
        if not wallets:
            await send(chat_id, "No wallets found. Submit a task first.")
            return
        lines = ["SOLANA DEVNET WALLETS\n─────────────────────"]
        for w in wallets[:8]:
            sol  = w.get("sol_address", "—")
            role = w.get("role", "?").upper()
            name = w.get("name", "?")
            bal  = float(w.get("balance", 0))
            cap  = float(w.get("budget_cap", 0))
            if sol and sol != "—":
                lines.append(
                    f"{name} [{role}]\n"
                    f"  {sol[:20]}…\n"
                    f"  Balance: {bal:.4f} / Cap: {cap:.2f} USDC"
                )
        rate_data = await _backend("/regis/meteora")
        if rate_data.get("rate"):
            lines.append(f"\nSOL/USDC: {rate_data['rate']} ({rate_data.get('source','')})")
        await send(chat_id, "\n".join(lines))
    except Exception as exc:
        await send(chat_id, f"Solana query failed: {exc}")


async def cmd_ows(chat_id: int):
    try:
        r = await _pb("/api/collections/wallets/records?sort=-created&perPage=10")
        wallets = r.get("items", [])
        if not wallets:
            await send(chat_id, "No OWS wallets found.")
            return
        lines = ["OWS WALLET PERMISSIONS\n──────────────────────"]
        for w in wallets[:8]:
            name    = w.get("name", "?")
            role    = w.get("role", "?").upper()
            eth     = w.get("eth_address", "—")
            api_key = w.get("api_key_id", "—")
            cap     = float(w.get("budget_cap", 0))
            revoked = "REVOKED" in str(api_key)
            status  = "✗ REVOKED" if revoked else "✓ ACTIVE"
            lines.append(
                f"{name} [{role}] {status}\n"
                f"  Addr: {eth[:16]}…  Cap: {cap:.4f} USDC"
            )
        lines.append(
            "\nPolicy: Rep gate → Budget cap → No double-pay\n"
            "  5★=$10 · 4★=$2 · 3★=$1 · 2★=$0.50"
        )
        await send(chat_id, "\n".join(lines))
    except Exception as exc:
        await send(chat_id, f"OWS query failed: {exc}")


async def cmd_model(chat_id: int):
    try:
        from services.model_service import current_routing_info
        info = current_routing_info()
        await send(chat_id,
            f"MODEL ROUTING\n"
            f"─────────────\n"
            f"Primary:    {info['primary_model']}\n"
            f"Governance: {info['governance_model']}\n"
            f"DeepSeek:   {'✓ ENABLED' if info['deepseek_enabled'] else '✗ KEY MISSING'}\n"
            f"Endpoint:   {info['deepseek_base']}\n\n"
            f"{info['note']}"
        )
    except Exception as exc:
        await send(chat_id, f"Model info failed: {exc}")


async def cmd_lock(chat_id: int, args: str):
    name = args.strip().upper()
    if not name:
        await send(chat_id, "Usage: /lock <AGENT>\nAgents: ATLAS · CIPHER · FORGE · BISHOP · SØN")
        return
    try:
        from services.agent_lock_service import lock_agent, VALID_AGENTS
        if name not in VALID_AGENTS:
            await send(chat_id, f"Unknown agent: {name}\nValid: {', '.join(VALID_AGENTS)}")
            return
        newly_locked = lock_agent(name, "Locked via Telegram")
        if newly_locked:
            await send(chat_id, f"🔒 {name} LOCKED\n{name} will be skipped in future tasks.\nUse /unlock {name} to reactivate.")
        else:
            await send(chat_id, f"{name} is already locked.")
    except Exception as exc:
        await send(chat_id, f"Lock failed: {exc}")


async def cmd_unlock(chat_id: int, args: str):
    name = args.strip().upper()
    if not name:
        await send(chat_id, "Usage: /unlock <AGENT>")
        return
    try:
        from services.agent_lock_service import unlock_agent, VALID_AGENTS
        if name not in VALID_AGENTS:
            await send(chat_id, f"Unknown agent: {name}\nValid: {', '.join(VALID_AGENTS)}")
            return
        was_locked = unlock_agent(name)
        if was_locked:
            await send(chat_id, f"🔓 {name} UNLOCKED\nAgent is active for future tasks.")
        else:
            await send(chat_id, f"{name} was not locked.")
    except Exception as exc:
        await send(chat_id, f"Unlock failed: {exc}")


async def cmd_locked(chat_id: int):
    try:
        from services.agent_lock_service import get_locked
        locked = get_locked()
        if not locked:
            await send(chat_id, "No agents are locked. All 5 are active.")
            return
        lines = ["LOCKED AGENTS\n─────────────"]
        for name, reason in locked.items():
            lines.append(f"🔒 {name}\n  Reason: {reason}")
        lines.append("\nUse /unlock <AGENT> to reactivate.")
        await send(chat_id, "\n".join(lines))
    except Exception as exc:
        await send(chat_id, f"Lock status failed: {exc}")


async def cmd_approve(chat_id: int, args: str):
    agent_id = args.strip().upper()
    if not agent_id:
        await send(chat_id, "Usage: /approve <AGENT>")
        return
    try:
        from services.sovereignty_service import sovereignty_service
        result = await asyncio.to_thread(sovereignty_service.resolve_overthrow, agent_id, True)
        await send(chat_id, f"👑 {result}")
    except Exception as exc:
        await send(chat_id, f"Approve failed: {exc}")


async def cmd_veto(chat_id: int, args: str):
    agent_id = args.strip().upper()
    if not agent_id:
        await send(chat_id, "Usage: /veto <AGENT>")
        return
    try:
        from services.sovereignty_service import sovereignty_service
        result = await asyncio.to_thread(sovereignty_service.resolve_overthrow, agent_id, False)
        await send(chat_id, f"⚔️ {result}")
    except Exception as exc:
        await send(chat_id, f"Veto failed: {exc}")


async def cmd_challenge(chat_id: int, args: str):
    challenger = args.strip().upper()
    if not challenger:
        await send(chat_id, "Usage: /challenge <AGENT>")
        return
    try:
        from services.quality_service import qualifies_for_challenge, run_regis_challenge, get_avg_quality
        from services.agent_lock_service import VALID_AGENTS
        if challenger not in VALID_AGENTS:
            await send(chat_id, f"Unknown agent: {challenger}")
            return

        r = await _pb("/api/collections/agent_reputation/records?perPage=10")
        recs = r.get("items", [])
        rep_map = {rec.get("agent_id"): float(rec.get("current_reputation", 3.0)) for rec in recs}
        rep = rep_map.get(challenger, 3.0)

        if not qualifies_for_challenge(challenger, rep):
            avg_q = get_avg_quality(challenger)
            await send(chat_id,
                f"⚔ {challenger} does not qualify.\n"
                f"Needs: avg quality ≥ 8.0 (have {avg_q:.1f}), rep ≥ 4.5★ (have {rep:.2f}★), ≥ 3 tasks."
            )
            return

        await send(chat_id, f"⚔ Challenge: {challenger} vs REGIS… convening tribunal.")
        brain_r = await _backend("/regis/brain")
        result  = await asyncio.to_thread(run_regis_challenge, challenger, brain_r.get("content", ""))

        winner  = result.get("winner", "REGIS")
        verdict = result.get("verdict", "")
        avg_q   = result.get("challenger_avg", 0)

        if winner == challenger:
            msg = (f"👑 THRONE CHANGES HANDS\n{challenger} DEFEATS REGIS!\n"
                   f"Quality avg: {avg_q:.1f}/10\nVerdict: {verdict}")
        else:
            msg = (f"⚔ REGIS PREVAILS\nDefeats {challenger}.\n"
                   f"Challenger avg: {avg_q:.1f}/10\nVerdict: {verdict}")
        await send(chat_id, msg)
    except Exception as exc:
        await send(chat_id, f"Challenge failed: {exc}")


async def cmd_dryrun(chat_id: int):
    os.environ["LIVE_MODE"] = "false"
    await send(chat_id, "DRY RUN MODE ACTIVE\nTransactions use mock signatures. Use /live for real devnet.")


async def cmd_live(chat_id: int):
    os.environ["LIVE_MODE"] = "true"
    await send(chat_id, "⚠ LIVE MODE ACTIVE\nReal Solana devnet transactions enabled. Use /dryrun to return.")


async def handle_plain_message(chat_id: int, text: str):
    try:
        r = await _backend("/regis/probe", "POST", {"question": text})
        answer = r.get("answer") or r.get("response") or "The court is temporarily closed."
        await send(chat_id, f"👑 REGIS:\n{answer}")
    except Exception:
        await send(chat_id, "The court is temporarily closed.")


# ── Message router ─────────────────────────────────────────────────────────────

async def handle_update(update: dict) -> None:
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return

    chat_id = msg.get("chat", {}).get("id")
    if not chat_id:
        return

    if ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID:
        await send(chat_id, "Access denied. This is a private REGIS terminal.")
        return

    text = (msg.get("text") or "").strip()
    if not text:
        return

    cmd  = text.split()[0].lower()
    args = text[len(cmd):].strip()

    if cmd in ("/start",):              await cmd_start(chat_id)
    elif cmd in ("/help",):             await cmd_help(chat_id)
    elif cmd in ("/deploy",):           await cmd_deploy(chat_id, args)
    elif cmd in ("/submit",):           await cmd_deploy(chat_id, args)   # alias
    elif cmd in ("/status",):           await cmd_status(chat_id, args)
    elif cmd in ("/probe",):            await cmd_probe(chat_id, args)
    elif cmd in ("/audit",):            await cmd_audit(chat_id)
    elif cmd in ("/punish",):           await cmd_punish(chat_id, args)
    elif cmd in ("/fund",):             await cmd_fund(chat_id, args)
    elif cmd in ("/treasury",):         await cmd_treasury(chat_id)
    elif cmd in ("/economy",):          await cmd_economy(chat_id)
    elif cmd in ("/logs",):             await cmd_logs(chat_id, args)
    elif cmd in ("/agents",):           await cmd_agents(chat_id)
    elif cmd in ("/balance",):          await cmd_balance(chat_id)
    elif cmd in ("/brain",):            await cmd_brain(chat_id)
    elif cmd in ("/reputations",):      await cmd_reputations(chat_id)
    elif cmd in ("/tasks",):            await cmd_tasks_list(chat_id)
    elif cmd in ("/solana",):           await cmd_solana(chat_id)
    elif cmd in ("/ows",):              await cmd_ows(chat_id)
    elif cmd in ("/moonpay",):          await cmd_fund(chat_id, args)     # alias
    elif cmd in ("/model",):            await cmd_model(chat_id)
    elif cmd in ("/dryrun",):           await cmd_dryrun(chat_id)
    elif cmd in ("/live",):             await cmd_live(chat_id)
    elif cmd in ("/lock",):             await cmd_lock(chat_id, args)
    elif cmd in ("/unlock",):           await cmd_unlock(chat_id, args)
    elif cmd in ("/locked",):           await cmd_locked(chat_id)
    elif cmd in ("/challenge",):        await cmd_challenge(chat_id, args)
    elif cmd in ("/veto",):             await cmd_veto(chat_id, args)
    elif cmd in ("/approve",):          await cmd_approve(chat_id, args)
    else:                               await handle_plain_message(chat_id, text)


# ── Polling loop ───────────────────────────────────────────────────────────────

async def poll_loop() -> None:
    """Long-poll Telegram for updates. Runs until cancelled. NO startup message."""
    if not TELEGRAM_TOKEN:
        logger.info("[telegram] No TELEGRAM_BOT_TOKEN — bot disabled")
        return

    logger.info("[telegram] REGIS bot starting silently (chat_id=%s)", ALLOWED_CHAT_ID)
    # ← No startup notification. First message user sees is their own /start.
    offset = 0

    async with httpx.AsyncClient(timeout=40.0) as client:
        while True:
            try:
                r = await client.get(
                    f"{_TG_API}/getUpdates",
                    params={"offset": offset, "timeout": 30, "allowed_updates": ["message"]},
                )
                if not r.is_success:
                    await asyncio.sleep(5)
                    continue

                for update in r.json().get("result", []):
                    offset = update["update_id"] + 1
                    try:
                        await handle_update(update)
                    except Exception:
                        traceback.print_exc()

            except asyncio.CancelledError:
                logger.info("[telegram] Bot stopped")
                return
            except Exception as exc:
                logger.warning("[telegram] poll error: %s", exc)
                await asyncio.sleep(5)
