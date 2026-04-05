"""
Quality Service — Claude evaluates each agent's work quality post-execution.

Evaluation uses a tight 80-token prompt via DeepSeek (cheap) to score
each agent's output relative to the overall task goal.

Score 0-10 scales the agent's payment:
  payment = budget_allocated * (score / 10)

Scores also feed the REGIS challenge system — sustained high-quality work
lets an agent compete for the coordinator role.

Token budget: ~80 tokens per evaluation call (DeepSeek).
"""

import json
import os
from typing import Dict, List
from collections import defaultdict

from services.model_service import call_deepseek, call_claude

# ── Cumulative quality tracking for REGIS challenge ───────────────────────────
# In-memory: {agent_name: [score, score, ...]}
_quality_history: Dict[str, List[float]] = defaultdict(list)

# REGIS challenge threshold
CHALLENGE_THRESHOLD_SCORE = 8.0   # avg quality across recent tasks
CHALLENGE_THRESHOLD_REP   = 4.5   # minimum reputation
CHALLENGE_MIN_TASKS       = 3     # minimum tasks before eligible


def evaluate_work(
    task_goal: str,
    agent_name: str,
    agent_output: str,
    context_preview: str = "",
) -> Dict:
    """
    Ask DeepSeek to score agent output quality relative to task goal.
    Returns {"score": float, "reason": str, "payment_multiplier": float}
    """
    # Tight prompt — ~80 tokens
    ctx = f"\nPrior work: {context_preview[:150]}" if context_preview else ""
    prompt = (
        f'Task goal: "{task_goal[:150]}"\n'
        f'{agent_name} output: "{agent_output[:400]}"{ctx}\n\n'
        "Score the agent output quality 0-10 based on:\n"
        "- Relevance to goal (does it actually address the mission?)\n"
        "- Depth and specificity (concrete data vs vague statements)\n"
        "- Actionability (can next agent build on this?)\n"
        f'JSON only: {{"score": 7, "reason": "2-sentence specific reason"}}'
    )
    try:
        raw = call_deepseek(prompt, max_tokens=120)
        s, e = raw.find("{"), raw.rfind("}") + 1
        if s != -1 and e > s:
            parsed = json.loads(raw[s:e])
            score = min(10.0, max(0.0, float(parsed.get("score", 5.0))))
            reason = str(parsed.get("reason", ""))[:120]
        else:
            score = 5.0
            reason = "evaluation parse failed"
    except Exception as exc:
        print(f"[quality] {agent_name}: {exc}")
        score = 5.0
        reason = "evaluation error"

    multiplier = round(score / 10.0, 3)
    _quality_history[agent_name].append(score)

    return {"score": score, "reason": reason, "payment_multiplier": multiplier}


def get_avg_quality(agent_name: str) -> float:
    hist = _quality_history.get(agent_name, [])
    if not hist:
        return 5.0
    # Weight recent tasks more heavily
    recent = hist[-10:]
    return round(sum(recent) / len(recent), 2)


def qualifies_for_challenge(agent_name: str, reputation: float) -> bool:
    hist = _quality_history.get(agent_name, [])
    if len(hist) < CHALLENGE_MIN_TASKS:
        return False
    if reputation < CHALLENGE_THRESHOLD_REP:
        return False
    return get_avg_quality(agent_name) >= CHALLENGE_THRESHOLD_SCORE


def run_regis_challenge(challenger_name: str, regis_brain_content: str) -> Dict:
    """
    Claude evaluates whether the challenger should take REGIS position.
    Returns {"winner": str, "score": float, "verdict": str}
    Fires a Telegram notification on both outcomes — especially REGIS overthrow.
    """
    challenger_scores = _quality_history.get(challenger_name, [])[-5:]
    avg = get_avg_quality(challenger_name)

    prompt = (
        f"REGIS governance record (last entries):\n{regis_brain_content[-600:]}\n\n"
        f"Challenger {challenger_name} recent work quality scores: {challenger_scores}\n"
        f"Challenger avg quality: {avg}/10\n\n"
        f"Should {challenger_name} replace REGIS as coordinator? "
        f"Consider: governance quality, decision consistency, rep track record.\n"
        f"Be decisive. If challenger scores are clearly superior, they win.\n"
        f'JSON only: {{"winner": "REGIS or {challenger_name}", "verdict": "reason in 2 sentences"}}'
    )
    winner  = "REGIS"
    verdict = "Challenge evaluation failed"
    try:
        raw = call_claude(prompt, max_tokens=150)
        s, e = raw.find("{"), raw.rfind("}") + 1
        if s != -1 and e > s:
            parsed = json.loads(raw[s:e])
            winner  = parsed.get("winner", "REGIS")
            verdict = parsed.get("verdict", "")
    except Exception as exc:
        print(f"[challenge] {exc}")

    result = {"winner": winner, "verdict": verdict, "challenger_avg": avg}

    # Telegram — fire and forget (sync context: use asyncio.create_task if in event loop)
    _fire_challenge_notification(challenger_name, winner, verdict, avg, challenger_scores)

    return result


def _fire_challenge_notification(
    challenger: str, winner: str, verdict: str, avg: float, scores: list
) -> None:
    """Send Telegram notification about challenge result (sync, best-effort)."""
    import asyncio
    try:
        from services.telegram_service import send, ALLOWED_CHAT_ID

        if winner != "REGIS":
            msg = (
                f"👑 REGIS OVERTHROWN!\n"
                f"══════════════════════\n"
                f"⚔️ Challenger: {challenger}\n"
                f"New Coordinator: {winner}\n"
                f"Avg Quality: {avg:.1f}/10\n"
                f"Recent scores: {scores}\n"
                f"─────────────────────\n"
                f"Verdict: {verdict}\n"
                f"REGIS has been dethroned. Long live {winner}."
            )
        else:
            msg = (
                f"⚔️ CHALLENGE DEFEATED\n"
                f"─────────────────────\n"
                f"{challenger} challenged REGIS and lost.\n"
                f"Challenger avg quality: {avg:.1f}/10\n"
                f"REGIS retains the crown.\n"
                f"Verdict: {verdict}"
            )

        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if loop and loop.is_running():
            loop.create_task(send(ALLOWED_CHAT_ID, msg))
        else:
            asyncio.run(send(ALLOWED_CHAT_ID, msg))
    except Exception as exc:
        print(f"[challenge tg] {exc}")
