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
        "/reputations      — agent scores\n"
        "/audit            — governance audit\n"
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
            f"5 agents deployed. Use /status to monitor.\n"
            f"ATLAS · CIPHER · FORGE · BISHOP · SØN"
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
        stars = {5.0: "●●●●●", 4.0: "●●●●○", 3.0: "●●●○○", 2.0: "●●○○○", 1.0: "●○○○○"}
        for rec in sorted(recs, key=lambda x: -float(x.get("current_reputation", 0))):
            rep = float(rec.get("current_reputation", 0))
            s = stars.get(round(rep), f"{rep:.1f}")
            name = rec.get("agent_id", "?")
            lines.append(f"{name:8} {s} {rep:.2f}★")
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
