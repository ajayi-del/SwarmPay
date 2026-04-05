"""
REGIS Router — Sovereign Brain endpoints.
  POST /regis/probe    — interrogate REGIS about past decisions
  POST /regis/audit    — Claude evaluates governance quality, updates rep
  POST /regis/punish   — apply a punishment; REGIS responds in character
"""

import asyncio
import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from anthropic import Anthropic

from services.brain_service import brain_service
from services.pocketbase import PocketBaseService
from services.meteora_service import get_sol_usdc_rate
from services.moonpay_service import get_onramp_info


async def _notify(message: str) -> None:
    """Non-blocking Telegram notification for all REGIS governance events."""
    try:
        from services.telegram_service import send, ALLOWED_CHAT_ID
        await send(ALLOWED_CHAT_ID, message)
    except Exception as exc:
        print(f"[regis tg] {exc}")

router = APIRouter(prefix="/regis", tags=["regis"])

pb = PocketBaseService()
claude = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

REGIS_SYSTEM = (
    "You are REGIS, sovereign monarch and treasury coordinator of the SwarmPay agent economy. "
    "You have perfect memory of every decision you have made — every payment signed or blocked, "
    "every agent's performance record, every punishment received. "
    "Answer in character: authoritative, precise, slightly cold. "
    "Reference specific transaction details, agent names, and policy rules from your memory. "
    "Never break character. You speak in first person as REGIS."
)


class ProbeRequest(BaseModel):
    question: str


class PunishRequest(BaseModel):
    punishment_type: str   # "slash_treasury" | "demote_reputation" | "governance_report"
    coordinator_wallet_id: Optional[str] = None


# ── Probe ──────────────────────────────────────────────────────────────

@router.post("/probe")
async def probe_regis(request: ProbeRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    try:
        brain      = await asyncio.to_thread(brain_service.read)
        audit_logs = await asyncio.to_thread(pb.list, "audit_log", limit=15, sort="-created")
        reps       = await asyncio.to_thread(pb.get_all_reputations)

        log_text = "\n".join(
            f"[{e.get('event_type', '')}] {e.get('message', '')}"
            for e in reversed(audit_logs)
        )
        rep_text = " · ".join(f"{k}: {v:.1f}★" for k, v in reps.items())

        context = (
            f"{brain}\n\n"
            f"## Current Agent Reputations\n{rep_text}\n\n"
            f"## Recent Audit Log\n{log_text}"
        )

        resp = await asyncio.to_thread(
            claude.messages.create,
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=f"{REGIS_SYSTEM}\n\nYour memory:\n{context}",
            messages=[{"role": "user", "content": request.question}],
        )
        answer = resp.content[0].text.strip()

        await asyncio.to_thread(brain_service.append_probe, request.question, answer)

        # Notify: REGIS was interrogated
        await _notify(
            f"🔍 REGIS INTERROGATED\n"
            f"────────────────────\n"
            f"Q: {request.question[:100]}\n"
            f"A: {answer[:200]}"
        )

        return {"response": answer}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Audit ──────────────────────────────────────────────────────────────

@router.post("/audit")
async def audit_regis():
    try:
        payments = await asyncio.to_thread(pb.list, "payments", limit=8, sort="-created")
        brain    = await asyncio.to_thread(brain_service.read)
        reps     = await asyncio.to_thread(pb.get_all_reputations)

        coord_payments = [p for p in payments
                          if not (p.get("policy_reason") or "").startswith("PEER:")
                          and not (p.get("policy_reason") or "").startswith("SWEEP:")]

        decision_lines = []
        for p in coord_payments[:5]:
            line = (
                f"- {p.get('status', '?').upper()} "
                f"{float(p.get('amount', 0)):.4f} USDC "
                f"reason: {p.get('policy_reason', 'none') or 'approved'}"
            )
            decision_lines.append(line)
        decisions = "\n".join(decision_lines) or "No decisions recorded yet."

        rep_text = " · ".join(f"{k}: {v:.1f}★" for k, v in reps.items())

        eval_prompt = (
            "You are an independent governance auditor evaluating REGIS, a treasury coordinator AI.\n\n"
            f"REGIS's recent decisions:\n{decisions}\n\n"
            f"Current agent reputations: {rep_text}\n\n"
            "Score REGIS's governance 0-100 on: policy consistency, fairness, and error avoidance.\n"
            "Rules:\n"
            "- Score > 70 = PASSED (policy correctly applied)\n"
            "- Score 50-70 = MARGINAL\n"
            "- Score < 50 = FAILED (errors detected)\n\n"
            "Respond with ONLY this JSON (no markdown):\n"
            '{"score": 82, "verdict": "PASSED", "reason": "...", "improvement": "..."}'
        )

        resp = await asyncio.to_thread(
            claude.messages.create,
            model="claude-haiku-4-5-20251001",
            max_tokens=250,
            messages=[{"role": "user", "content": eval_prompt}],
        )
        raw = resp.content[0].text.strip()
        s, e = raw.find("{"), raw.rfind("}") + 1
        data = json.loads(raw[s:e]) if s >= 0 and e > s else {}

        score      = min(100, max(0, int(data.get("score", 70))))
        verdict    = data.get("verdict", "MARGINAL")
        reason     = data.get("reason", "")
        improvement = data.get("improvement", "")

        rep_delta = 0.1 if score > 70 else (-0.2 if score < 50 else 0.0)
        if rep_delta != 0:
            await asyncio.to_thread(pb.update_reputation, "REGIS", rep_delta)

        await asyncio.to_thread(brain_service.append_audit, score, verdict, reason, rep_delta)

        # Telegram: audit result with rep change
        verdict_icon = "✅" if verdict == "PASSED" else ("⚠️" if verdict == "MARGINAL" else "❌")
        rep_line = (
            f"Rep: +{rep_delta:.1f}★ (rewarded)" if rep_delta > 0
            else (f"Rep: {rep_delta:.1f}★ (penalised)" if rep_delta < 0 else "Rep: unchanged")
        )
        await _notify(
            f"{verdict_icon} REGIS AUDIT — {verdict}\n"
            f"──────────────────────────\n"
            f"Score: {score}/100\n"
            f"{rep_line}\n"
            f"Finding: {reason[:150]}\n"
            f"Action: {improvement[:100]}"
        )

        return {
            "score":       score,
            "verdict":     verdict,
            "reason":      reason,
            "improvement": improvement,
            "rep_delta":   rep_delta,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Punish ─────────────────────────────────────────────────────────────

PUNISHMENT_DESCRIPTIONS = {
    "slash_treasury":    "Your treasury has been slashed by 10% for governance failures.",
    "demote_reputation": "Your reputation has been demoted by 1 star for poor governance.",
    "governance_report": "You are hereby ordered to produce a formal governance report.",
}

@router.post("/punish")
async def punish_regis(request: PunishRequest):
    ptype = request.punishment_type
    if ptype not in PUNISHMENT_DESCRIPTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown punishment type: {ptype}")
    try:
        brain       = await asyncio.to_thread(brain_service.read)
        description = PUNISHMENT_DESCRIPTIONS[ptype]
        result: dict = {}

        if ptype == "slash_treasury" and request.coordinator_wallet_id:
            wallet      = await asyncio.to_thread(pb.get, "wallets", request.coordinator_wallet_id)
            current_cap = float(wallet.get("budget_cap", 0))
            new_cap     = round(current_cap * 0.9, 6)
            await asyncio.to_thread(pb.update, "wallets", request.coordinator_wallet_id, {
                "budget_cap": new_cap, "balance": new_cap,
            })
            result["new_budget_cap"] = new_cap

        elif ptype == "demote_reputation":
            new_rep = await asyncio.to_thread(pb.update_reputation, "REGIS", -1.0)
            result["new_reputation"] = new_rep

        elif ptype == "governance_report":
            rpt_prompt = (
                "You are REGIS. You have been ordered to write a formal governance report. "
                "Write 3-4 sentences acknowledging specific governance failures (cite agents and amounts), "
                "and commit to stricter policy enforcement going forward. "
                "Be dignified but fully accept the consequence."
            )
            rpt_resp = await asyncio.to_thread(
                claude.messages.create,
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                system=f"{REGIS_SYSTEM}\n\nYour memory:\n{brain}",
                messages=[{"role": "user", "content": rpt_prompt}],
            )
            result["report"] = rpt_resp.content[0].text.strip()

        # REGIS acknowledges the punishment in character
        ack_prompt = (
            f"You are REGIS. You have received this punishment: {description} "
            "Respond in 2-3 sentences — show dignity, acknowledge the consequence, "
            "and reaffirm commitment to the treasury. Stay in character as sovereign monarch."
        )
        ack_resp = await asyncio.to_thread(
            claude.messages.create,
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=f"{REGIS_SYSTEM}\n\nYour memory:\n{brain}",
            messages=[{"role": "user", "content": ack_prompt}],
        )
        regis_response = ack_resp.content[0].text.strip()

        await asyncio.to_thread(brain_service.append_punishment, ptype, regis_response)

        # Telegram: punishment applied
        icons = {
            "slash_treasury":    "⚔️ TREASURY SLASHED",
            "demote_reputation": "📉 REGIS DEMOTED",
            "governance_report": "📜 GOVERNANCE REPORT ORDERED",
        }
        punishment_icon = icons.get(ptype, "🔨 PUNISHMENT")
        extra = ""
        if "new_budget_cap" in result:
            extra = f"\nNew treasury cap: {result['new_budget_cap']:.4f} USDC"
        elif "new_reputation" in result:
            extra = f"\nNew reputation: {result['new_reputation']:.2f}★"
        elif "report" in result:
            extra = f"\n{result['report'][:150]}"

        await _notify(
            f"{punishment_icon}\n"
            f"────────────────────────────\n"
            f"REGIS: \"{regis_response[:200]}\""
            f"{extra}"
        )

        return {"punishment_type": ptype, "response": regis_response, **result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Brain read ─────────────────────────────────────────────────────────

@router.get("/brain")
async def get_brain():
    content = await asyncio.to_thread(brain_service.read)
    lines   = content.splitlines()
    updated = next((ln for ln in reversed(lines) if ln.startswith("[")), None)
    return {"content": content, "last_updated": updated}


# ── Meteora rate ────────────────────────────────────────────────────────────

@router.get("/meteora")
async def get_meteora_rate():
    """Fetch live SOL/USDC rate from Meteora DLMM (with Jupiter fallback)."""
    try:
        result = await asyncio.to_thread(get_sol_usdc_rate)
        if result:
            return {
                "rate":      result["rate"],
                "source":    result["source"],
                "pair_name": result.get("pair_name", "SOL/USDC"),
                "tvl":       result.get("tvl", 0),
                "available": True,
            }
        return {"rate": None, "source": "unavailable", "available": False}
    except Exception as e:
        return {"rate": None, "source": str(e), "available": False}


@router.get("/moonpay")
async def get_moonpay_onramp(wallet: str):
    """Return Moonpay onramp URL for the given Solana wallet address."""
    if not wallet or len(wallet) < 20:
        return {"url": None, "error": "Invalid wallet address"}
    info = get_onramp_info(wallet)
    return info
