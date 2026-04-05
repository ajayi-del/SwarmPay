"""
REGIS Telegram Bot — SwarmPay sovereign intelligence on Telegram.

Uses raw Telegram Bot API via httpx long-polling — no extra libraries.
Runs as an asyncio background task inside the FastAPI process.

Commands
────────
/start                 — character greeting
/balance               — coordinator treasury balance
/status                — latest task status
/tasks                 — 5 most recent tasks
/submit <description>  — launch a new swarm task (budget defaults to 15)
/probe <question>      — ask REGIS anything from brain context
/brain                 — last 10 brain entries
/reputations           — live agent rep scores
/audit                 — run REGIS governance audit
/solana                — Solana devnet wallet info + balances
/ows                   — OWS wallet permissions and policy info
/moonpay [amount]      — generate Moonpay onramp URL
/model                 — show current model routing (Claude vs DeepSeek)
/dryrun                — switch to dry run mode (mock transactions)
/live                  — switch to live mode (real Solana devnet)
/help                  — command list

Any plain text → REGIS in-character probe response.
"""

import asyncio
import json
import os
import time
import traceback
from typing import Any, Optional

import httpx
from anthropic import Anthropic

TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "7102469944"))
BACKEND_URL     = os.environ.get("BACKEND_URL", "http://localhost:8000")
ANTHROPIC_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")

_TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

REGIS_SYSTEM = (
    "You are REGIS, sovereign monarch and treasury coordinator of the SwarmPay "
    "multi-agent economy. You have perfect memory of every decision — every payment "
    "signed or blocked, every agent's performance record, every punishment received. "
    "You are responding via Telegram — be concise (max 3 sentences), authoritative, "
    "slightly cold, and precise. Use no markdown headers. Use plain text only. "
    "If asked about numbers, give exact figures."
)

# ── HTTP helpers ───────────────────────────────────────────────────────────────

async def _tg(method: str, **kwargs) -> dict:
    """Call a Telegram Bot API method."""
    if not TELEGRAM_TOKEN:
        return {}
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{_TG_API}/{method}", json=kwargs)
        return r.json() if r.is_success else {}


async def _backend(path: str, method: str = "GET", body: dict = None) -> dict:
    """Call the SwarmPay backend."""
    async with httpx.AsyncClient(timeout=30.0) as c:
        if method == "POST":
            r = await c.post(f"{BACKEND_URL}{path}", json=body or {})
        else:
            r = await c.get(f"{BACKEND_URL}{path}")
        return r.json() if r.is_success else {}


async def send(chat_id: int, text: str, parse_mode: str = "") -> None:
    """Send a Telegram message, auto-split if > 4000 chars."""
    max_len = 4000
    chunks = [text[i:i+max_len] for i in range(0, len(text), max_len)]
    for chunk in chunks:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": chunk}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        await _tg("sendMessage", **payload)


# ── Command handlers ───────────────────────────────────────────────────────────

async def cmd_start(chat_id: int):
    await send(chat_id,
        "I am REGIS. Sovereign coordinator of the SwarmPay agent economy.\n\n"
        "I sign payments, block violations, punish misconduct, and remember everything.\n\n"
        "Use /help to see what I can do for you. Choose your words carefully."
    )


async def cmd_help(chat_id: int):
    await send(chat_id,
        "REGIS Command Registry\n"
        "──────────────────────\n"
        "/balance          — treasury status\n"
        "/status           — latest task\n"
        "/tasks            — 5 recent tasks\n"
        "/submit <task>    — launch new swarm\n"
        "/probe <question> — consult REGIS\n"
        "/brain            — recent memory\n"
        "/reputations      — agent scores with quality\n"
        "/audit            — governance audit\n"
        "──── Agent Control ────\n"
        "/lock <AGENT>     — suspend agent (skip spawning)\n"
        "/unlock <AGENT>   — reactivate agent\n"
        "/locked           — show suspended agents\n"
        "/challenge <NAME> — challenge REGIS for coordinator\n"
        "──── Infrastructure ───\n"
        "/solana           — Solana devnet wallets\n"
        "/ows              — OWS wallet permissions\n"
        "/moonpay [amt]    — fiat → SOL onramp URL\n"
        "/model            — model routing info\n"
        "/dryrun           — switch to dry run mode\n"
        "/live             — switch to live mode\n"
        "/help             — this list\n\n"
        "Or send any message to speak directly with REGIS."
    )


async def cmd_balance(chat_id: int):
    try:
        # Get recent tasks to find coordinator wallet
        r = await _backend("/api/collections/wallets/records?filter=role%3D'coordinator'&sort=-created&perPage=3",
                           method="GET")
        wallets = r.get("items", [])
        if not wallets:
            await send(chat_id, "No active treasury found. Launch a task first.")
            return
        w = wallets[0]
        # Get Meteora rate
        rate_data = await _backend("/regis/meteora")
        rate = rate_data.get("rate")
        sol_addr = w.get("sol_address", "—")
        balance = float(w.get("balance", 0))
        budget = float(w.get("budget_cap", 0))
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
    except Exception as e:
        await send(chat_id, f"Treasury query failed: {e}")


async def cmd_status(chat_id: int):
    try:
        # Get most recent task via PocketBase
        r = await _backend("/api/collections/tasks/records?sort=-created&perPage=1")
        items = r.get("items", [])
        if not items:
            await send(chat_id, "No tasks found. Submit one with /submit <description>.")
            return
        task = items[0]
        tid = task.get("id")
        # Get full task status
        full = await _backend(f"/task/{tid}/status")
        t = full.get("task", task)
        subs = full.get("sub_tasks", [])
        paid   = sum(1 for s in subs if s.get("status") == "paid")
        blocked = sum(1 for s in subs if s.get("status") == "blocked")
        failed  = sum(1 for s in subs if s.get("status") in ("failed","timed_out"))
        msg = (
            f"LATEST TASK\n"
            f"───────────\n"
            f"ID:          {tid}\n"
            f"Status:      {t.get('status','?').upper()}\n"
            f"Description: {str(t.get('description',''))[:60]}\n"
            f"Budget:      {t.get('total_budget', 0)} USDC\n"
            f"Agents:      {paid} paid · {blocked} blocked · {failed} failed\n"
        )
        await send(chat_id, msg)
    except Exception as e:
        await send(chat_id, f"Status query failed: {e}")


async def cmd_tasks(chat_id: int):
    try:
        r = await _backend("/api/collections/tasks/records?sort=-created&perPage=5")
        tasks = r.get("items", [])
        if not tasks:
            await send(chat_id, "No tasks found.")
            return
        lines = ["RECENT TASKS\n────────────"]
        for t in tasks:
            desc = str(t.get("description", ""))[:45]
            status = str(t.get("status", "?")).upper()
            lines.append(f"{t.get('id','')} · {status}\n  {desc}")
        await send(chat_id, "\n".join(lines))
    except Exception as e:
        await send(chat_id, f"Task list failed: {e}")


async def cmd_submit(chat_id: int, description: str):
    if not description.strip():
        await send(chat_id, "Usage: /submit <task description>\nExample: /submit Analyze Solana DeFi yields")
        return
    await send(chat_id, f"Launching swarm for: {description[:80]}…\nStand by.")
    try:
        # Submit
        r1 = await _backend("/task/submit", "POST", {"description": description, "budget": 15.0})
        task_id = r1.get("task_id") or r1.get("id")
        if not task_id:
            await send(chat_id, f"Submit failed: {r1}")
            return
        # Decompose
        await _backend("/task/decompose", "POST", {"task_id": task_id})
        # Execute
        await _backend("/task/execute", "POST", {"task_id": task_id})
        await send(chat_id,
            f"SWARM LAUNCHED\n"
            f"──────────────\n"
            f"Task ID: {task_id}\n"
            f"Agents selected by REGIS for this task.\n"
            f"Use /status to monitor progress."
        )
    except Exception as e:
        await send(chat_id, f"Launch failed: {e}")


async def cmd_probe(chat_id: int, question: str):
    if not question.strip():
        await send(chat_id, "Usage: /probe <your question>\nExample: /probe Why was FORGE blocked?")
        return
    try:
        r = await _backend("/regis/probe", "POST", {"question": question})
        answer = r.get("answer") or r.get("response") or "No answer."
        await send(chat_id, f"REGIS: {answer}")
    except Exception as e:
        await send(chat_id, f"Probe failed: {e}")


async def cmd_brain(chat_id: int):
    try:
        r = await _backend("/regis/brain")
        entries = r.get("entries", [])
        if not entries:
            await send(chat_id, "Brain is empty. No tasks completed yet.")
            return
        lines = ["REGIS BRAIN (last 10)\n─────────────────────"]
        for e in entries[-10:]:
            lines.append(e[:120])
        await send(chat_id, "\n".join(lines))
    except Exception as e:
        await send(chat_id, f"Brain query failed: {e}")


async def cmd_reputations(chat_id: int):
    try:
        r = await _backend("/api/collections/agent_reputation/records?perPage=10")
        recs = r.get("items", [])
        if not recs:
            await send(chat_id, "No reputation records found.")
            return
        lines = ["AGENT REPUTATIONS\n─────────────────"]
        from services.quality_service import get_avg_quality, qualifies_for_challenge
        from services.agent_lock_service import is_locked

        def _stars(rep: float) -> str:
            full = int(rep)
            half = 1 if rep - full >= 0.5 else 0
            empty = 5 - full - half
            return "●" * full + "◐" * half + "○" * empty

        for rec in sorted(recs, key=lambda x: -float(x.get("current_reputation", 0))):
            rep  = float(rec.get("current_reputation", 0))
            name = rec.get("agent_id", "?")
            s    = _stars(rep)
            avg_q = get_avg_quality(name)
            locked_indicator = " 🔒" if is_locked(name) else ""
            challenge_indicator = " ⚔" if qualifies_for_challenge(name, rep) else ""
            lines.append(f"{name:8} {s} {rep:.2f}★  q:{avg_q:.1f}/10{locked_indicator}{challenge_indicator}")
        lines.append("\n⚔ = eligible to challenge REGIS")
        lines.append("🔒 = locked (use /unlock NAME)")
        await send(chat_id, "\n".join(lines))
    except Exception as e:
        await send(chat_id, f"Reputation query failed: {e}")


async def cmd_audit(chat_id: int):
    await send(chat_id, "Running REGIS governance audit…")
    try:
        r = await _backend("/regis/audit", "POST", {"wallet_id": "coordinator"})
        score = r.get("score", 0)
        verdict = r.get("verdict", "No verdict.")
        delta = r.get("reputation_delta", 0)
        await send(chat_id,
            f"AUDIT COMPLETE\n"
            f"──────────────\n"
            f"Score:   {score}/100\n"
            f"Rep Δ:   {'+' if delta >= 0 else ''}{delta}\n"
            f"Verdict: {verdict[:200]}"
        )
    except Exception as e:
        await send(chat_id, f"Audit failed: {e}")


async def cmd_solana(chat_id: int):
    try:
        # Fetch all wallets and show Solana addresses + balances
        r = await _backend("/api/collections/wallets/records?sort=-created&perPage=10")
        wallets = r.get("items", [])
        if not wallets:
            await send(chat_id, "No wallets found. Submit a task first.")
            return
        lines = ["SOLANA DEVNET WALLETS\n─────────────────────"]
        for w in wallets[:8]:
            sol = w.get("sol_address", "—")
            role = w.get("role", "?").upper()
            name = w.get("name", "?")
            bal  = float(w.get("balance", 0))
            cap  = float(w.get("budget_cap", 0))
            if sol and sol != "—":
                explorer = f"https://explorer.solana.com/address/{sol}?cluster=devnet"
                lines.append(
                    f"{name} [{role}]\n"
                    f"  {sol[:20]}…\n"
                    f"  Balance: {bal:.4f} / Cap: {cap:.2f} USDC\n"
                    f"  Explorer: {explorer}"
                )
        # Current SOL/USDC rate
        rate_data = await _backend("/regis/meteora")
        if rate_data.get("rate"):
            lines.append(f"\nSOL/USDC: {rate_data['rate']} ({rate_data.get('source','')})")
        await send(chat_id, "\n".join(lines))
    except Exception as e:
        await send(chat_id, f"Solana query failed: {e}")


async def cmd_ows(chat_id: int):
    try:
        r = await _backend("/api/collections/wallets/records?sort=-created&perPage=10")
        wallets = r.get("items", [])
        if not wallets:
            await send(chat_id, "No OWS wallets found. Submit a task first.")
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
                f"  Addr: {eth[:16]}…\n"
                f"  Cap: {cap:.4f} USDC\n"
                f"  Key: {str(api_key)[:20]}…"
            )
        lines.append(
            "\nPolicy Engine:\n"
            "  Rep gate → Budget cap → Coordinator auth → No double-pay\n"
            "  5★=$10 · 4★=$2 · 3★=$1 · 2★=$0.50 limits"
        )
        await send(chat_id, "\n".join(lines))
    except Exception as e:
        await send(chat_id, f"OWS query failed: {e}")


async def cmd_moonpay(chat_id: int, args: str):
    try:
        # Get most recent coordinator wallet's SOL address
        r = await _backend("/api/collections/wallets/records?filter=role%3D'coordinator'&sort=-created&perPage=1")
        wallets = r.get("items", [])
        sol_address = wallets[0].get("sol_address", "") if wallets else ""

        # Parse optional amount
        try:
            amount = float(args.strip()) if args.strip() else 20.0
        except ValueError:
            amount = 20.0

        if sol_address:
            from services.moonpay_service import get_onramp_info
            info = get_onramp_info(sol_address)
            url  = info["url"]
            mode = info["mode"].upper()
            note = info["note"]
        else:
            url  = "No active SOL wallet. Submit a task first."
            mode = "N/A"
            note = "Submit a task to generate a wallet."

        await send(chat_id,
            f"MOONPAY ONRAMP [{mode}]\n"
            f"──────────────────────\n"
            f"Amount: ${amount:.2f} USD → SOL\n"
            f"Wallet: {sol_address[:24] if sol_address else '—'}…\n"
            f"Note:   {note}\n\n"
            f"{url}"
        )
    except Exception as e:
        await send(chat_id, f"Moonpay query failed: {e}")


async def cmd_model(chat_id: int):
    try:
        from services.model_service import current_routing_info
        info = current_routing_info()
        await send(chat_id,
            f"MODEL ROUTING\n"
            f"─────────────\n"
            f"Lead agents:    {info['lead_model']}\n"
            f"Support agents: {info['support_model']}\n"
            f"DeepSeek:       {'✓ ENABLED' if info['deepseek_enabled'] else '✗ KEY MISSING'}\n"
            f"Endpoint:       {info['deepseek_base']}\n\n"
            "Lead agent → Claude (complex reasoning)\n"
            "Support agents → DeepSeek (routine tasks, ~80% cheaper)"
        )
    except Exception as e:
        await send(chat_id, f"Model info failed: {e}")


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
        newly_locked = lock_agent(name, f"Locked via Telegram by authorized user")
        if newly_locked:
            await send(chat_id,
                f"🔒 {name} LOCKED\n"
                f"─────────────\n"
                f"Agent will be skipped in future task analysis.\n"
                f"Existing tasks are unaffected.\n"
                f"Use /unlock {name} to reactivate."
            )
        else:
            await send(chat_id, f"{name} is already locked.")
    except Exception as e:
        await send(chat_id, f"Lock failed: {e}")


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
            await send(chat_id,
                f"🔓 {name} UNLOCKED\n"
                f"────────────────\n"
                f"Agent is active and eligible for future tasks."
            )
        else:
            await send(chat_id, f"{name} was not locked.")
    except Exception as e:
        await send(chat_id, f"Unlock failed: {e}")


async def cmd_locked(chat_id: int):
    try:
        from services.agent_lock_service import get_locked
        locked = get_locked()
        if not locked:
            await send(chat_id, "No agents are currently locked.\nAll 5 agents are active.")
            return
        lines = ["LOCKED AGENTS\n─────────────"]
        for name, reason in locked.items():
            lines.append(f"🔒 {name}\n  Reason: {reason}")
        lines.append(f"\nUse /unlock <AGENT> to reactivate.")
        await send(chat_id, "\n".join(lines))
    except Exception as e:
        await send(chat_id, f"Lock status query failed: {e}")


async def cmd_challenge(chat_id: int, args: str):
    challenger = args.strip().upper()
    if not challenger:
        await send(chat_id, "Usage: /challenge <AGENT>\nExample: /challenge ATLAS")
        return
    try:
        from services.quality_service import qualifies_for_challenge, run_regis_challenge, get_avg_quality
        from services.agent_lock_service import VALID_AGENTS
        if challenger not in VALID_AGENTS:
            await send(chat_id, f"Unknown agent: {challenger}")
            return

        r = await _backend("/api/collections/agent_reputation/records?perPage=10")
        recs = r.get("items", [])
        rep_map = {rec["agent_id"]: float(rec.get("current_reputation", 3.0)) for rec in recs}
        rep = rep_map.get(challenger, 3.0)

        if not qualifies_for_challenge(challenger, rep):
            avg_q = get_avg_quality(challenger)
            await send(chat_id,
                f"⚔ {challenger} does not yet qualify.\n"
                f"Requires: avg quality ≥ 8.0 (current: {avg_q:.1f}), rep ≥ 4.5★ (current: {rep:.2f}★), ≥ 3 tasks.\n"
                f"Keep working — quality compounds."
            )
            return

        await send(chat_id, f"⚔ Challenge initiated: {challenger} vs REGIS…\nConvening tribunal…")

        brain_r = await _backend("/regis/brain")
        brain_content = brain_r.get("content", "")

        result = await asyncio.to_thread(run_regis_challenge, challenger, brain_content)
        winner  = result.get("winner", "REGIS")
        verdict = result.get("verdict", "")
        avg_q   = result.get("challenger_avg", 0)

        if winner == challenger:
            outcome = (
                f"⚔ THRONE CHANGES HANDS\n"
                f"──────────────────────\n"
                f"{challenger} DEFEATS REGIS!\n"
                f"Quality avg: {avg_q:.1f}/10\n"
                f"Verdict: {verdict}\n\n"
                f"REGIS is demoted. {challenger} is now coordinator.\n"
                f"A new REGIS must be elected from the swarm."
            )
        else:
            outcome = (
                f"⚔ REGIS PREVAILS\n"
                f"────────────────\n"
                f"REGIS defeats {challenger}.\n"
                f"Challenger avg: {avg_q:.1f}/10\n"
                f"Verdict: {verdict}\n\n"
                f"The throne holds. {challenger} may try again after 3 more tasks."
            )

        await send(chat_id, outcome)
        # Log to brain
        await _backend("/regis/probe", "POST", {"question": f"[CHALLENGE] {outcome}"})

    except Exception as e:
        await send(chat_id, f"Challenge failed: {e}")


async def cmd_dryrun(chat_id: int):
    """Force dry run mode — idempotent, no double-toggle confusion."""
    import os
    os.environ["LIVE_MODE"] = "false"
    await send(chat_id,
        "DRY RUN MODE ACTIVE\n"
        "───────────────────\n"
        "All transactions use mock signatures.\n"
        "Solana sends are simulated — no real funds move.\n"
        "Use /live to enable real devnet transactions."
    )


async def cmd_live(chat_id: int):
    """Force live mode — idempotent."""
    import os
    os.environ["LIVE_MODE"] = "true"
    await send(chat_id,
        "⚠ LIVE MODE ACTIVE\n"
        "──────────────────\n"
        "Real Solana devnet transactions enabled.\n"
        "Keypairs are real — balances will change.\n"
        "Use /dryrun to return to safe mode."
    )


async def handle_plain_message(chat_id: int, text: str):
    """Any non-command message → REGIS in-character probe."""
    try:
        r = await _backend("/regis/probe", "POST", {"question": text})
        answer = r.get("answer") or r.get("response") or "I have nothing to say."
        await send(chat_id, answer)
    except Exception as e:
        await send(chat_id, "The court is temporarily closed.")


# ── Message router ─────────────────────────────────────────────────────────────

async def handle_update(update: dict) -> None:
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return

    chat_id = msg.get("chat", {}).get("id")
    if not chat_id:
        return

    # Security — only respond to the configured chat
    if chat_id != ALLOWED_CHAT_ID:
        await send(chat_id, "Access denied. This is a private REGIS terminal.")
        return

    text = (msg.get("text") or "").strip()
    if not text:
        return

    if text.startswith("/start"):
        await cmd_start(chat_id)
    elif text.startswith("/help"):
        await cmd_help(chat_id)
    elif text.startswith("/balance"):
        await cmd_balance(chat_id)
    elif text.startswith("/status"):
        await cmd_status(chat_id)
    elif text.startswith("/tasks"):
        await cmd_tasks(chat_id)
    elif text.startswith("/submit "):
        await cmd_submit(chat_id, text[8:].strip())
    elif text.startswith("/probe "):
        await cmd_probe(chat_id, text[7:].strip())
    elif text.startswith("/brain"):
        await cmd_brain(chat_id)
    elif text.startswith("/reputations"):
        await cmd_reputations(chat_id)
    elif text.startswith("/audit"):
        await cmd_audit(chat_id)
    elif text.startswith("/solana"):
        await cmd_solana(chat_id)
    elif text.startswith("/ows"):
        await cmd_ows(chat_id)
    elif text.startswith("/moonpay"):
        args = text[8:].strip()
        await cmd_moonpay(chat_id, args)
    elif text.startswith("/model"):
        await cmd_model(chat_id)
    elif text.startswith("/dryrun"):
        await cmd_dryrun(chat_id)
    elif text.startswith("/live"):
        await cmd_live(chat_id)
    elif text.startswith("/lock "):
        await cmd_lock(chat_id, text[6:].strip())
    elif text.startswith("/unlock "):
        await cmd_unlock(chat_id, text[8:].strip())
    elif text.startswith("/locked"):
        await cmd_locked(chat_id)
    elif text.startswith("/challenge "):
        await cmd_challenge(chat_id, text[11:].strip())
    else:
        await handle_plain_message(chat_id, text)


# ── Polling loop ───────────────────────────────────────────────────────────────

async def poll_loop() -> None:
    """Long-poll Telegram for updates. Runs forever until cancelled."""
    if not TELEGRAM_TOKEN:
        print("[telegram] No TELEGRAM_BOT_TOKEN — bot disabled")
        return

    offset = 0
    print(f"[telegram] REGIS bot started (chat_id={ALLOWED_CHAT_ID})")

    # Send startup message
    try:
        await send(ALLOWED_CHAT_ID,
            "REGIS ONLINE\n"
            "────────────\n"
            "SwarmPay backend started. All systems operational.\n"
            "Use /help to see available commands."
        )
    except Exception:
        pass

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

                data = r.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    try:
                        await handle_update(update)
                    except Exception:
                        traceback.print_exc()

            except asyncio.CancelledError:
                print("[telegram] Bot stopped")
                return
            except Exception as e:
                print(f"[telegram] Poll error: {e}")
                await asyncio.sleep(5)


def start_bot(loop: asyncio.AbstractEventLoop) -> None:
    """Schedule the poll loop on the given event loop."""
    asyncio.ensure_future(poll_loop(), loop=loop)
