"""
Bounty Service — Autonomous agent economy.

Turns SwarmPay into a self-sustaining miniature economy:
  • User tasks become open bounties on a public board
  • Agents bid autonomously based on reputation + relevant skills
  • REGIS awards to highest-rep lowest-bid combination
  • BISHOP fines agents for policy violations (10% of balance)
  • REGIS decrees austerity/prosperity based on treasury health
  • CIPHER yield proposals filed when APR > 7%

Requires PocketBase collections: bounties, proposals, decrees, fines
(Create via admin UI or let this service create them lazily.)

All methods degrade gracefully — never crash the main pipeline.
"""

import logging
import time
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

logger = logging.getLogger("swarmpay.bounty")

# Agent skill weights for bounty matching
_AGENT_SKILLS: dict[str, list[str]] = {
    "ATLAS":  ["research", "news", "intel", "data", "search", "analysis", "monitor"],
    "CIPHER": ["yield", "defi", "apr", "pool", "farming", "protocol", "score"],
    "FORGE":  ["write", "report", "content", "synthesis", "document", "draft"],
    "BISHOP": ["compliance", "audit", "risk", "legal", "governance", "policy"],
    "SØN":    ["track", "balance", "wallet", "treasury", "fund", "solana"],
}

_TREASURY_AUSTERITY_THRESHOLD = 0.5    # SOL — below this → austerity decree
_TREASURY_PROSPERITY_THRESHOLD = 5.0   # SOL — above this → prosperity decree
_REGIS_TAX_RATE = Decimal("0.02")      # 2% on all PEER transfers → treasury
_BISHOP_FINE_PCT = Decimal("0.10")     # 10% of agent balance on violation
_BISHOP_KEEPER_PCT = Decimal("0.10")   # BISHOP earns 10% of fine collected
_CIPHER_COMMISSION_PCT = Decimal("0.10") # CIPHER earns 10% on yield proposals


# ── Bounty Board ────────────────────────────────────────────────────────────────

def create_bounty(pb, task_id: str, description: str, budget_usdc: float) -> Optional[dict]:
    """
    Convert a submitted task into an open bounty on the board.
    Agents will see this and bid autonomously.
    """
    try:
        bounty = pb.create("bounties", {
            "task_id":     task_id,
            "title":       description[:120],
            "budget_usdc": budget_usdc,
            "priority":    _score_priority(description, budget_usdc),
            "status":      "open",
            "bids":        [],
        })
        logger.info("[bounty] created: %s (%.2f USDC)", task_id[:8], budget_usdc)
        return bounty
    except Exception as exc:
        logger.debug("[bounty] create: %s", exc)
        return None


def agent_bid(
    pb,
    bounty_id: str,
    agent_name: str,
    reputation: float,
    bid_usdc: float,
) -> bool:
    """Agent places a bid on an open bounty."""
    try:
        bounty = pb.get("bounties", bounty_id)
        if bounty.get("status") != "open":
            return False

        skill_match = _skill_match_score(agent_name, bounty.get("title", ""))
        bids = bounty.get("bids") or []
        bids.append({
            "agent":       agent_name,
            "bid_usdc":    bid_usdc,
            "reputation":  reputation,
            "skill_match": skill_match,
            "timestamp":   int(time.time()),
        })
        pb.update("bounties", bounty_id, {"bids": bids, "status": "bidding"})
        logger.debug("[bounty] %s bid %.4f USDC on %s", agent_name, bid_usdc, bounty_id[:8])
        return True
    except Exception as exc:
        logger.debug("[bounty] bid: %s", exc)
        return False


def award_bounty(pb, bounty_id: str) -> Optional[str]:
    """
    REGIS awards bounty to highest rep × skill_match / bid_usdc ratio.
    Returns winning agent name.
    """
    try:
        bounty = pb.get("bounties", bounty_id)
        bids = bounty.get("bids") or []
        if not bids:
            return None

        def score(bid: dict) -> float:
            rep = float(bid.get("reputation", 1))
            skill = float(bid.get("skill_match", 0.5))
            bid_amt = max(float(bid.get("bid_usdc", 0.01)), 0.001)
            return (rep * skill) / bid_amt

        winner = max(bids, key=score)
        agent = winner["agent"]
        pb.update("bounties", bounty_id, {
            "status":    "awarded",
            "awarded_to": agent,
        })
        logger.info("[bounty] awarded %s → %s", bounty_id[:8], agent)
        return agent
    except Exception as exc:
        logger.debug("[bounty] award: %s", exc)
        return None


# ── REGIS Decrees ───────────────────────────────────────────────────────────────

def maybe_issue_decree(pb, treasury_sol: float) -> Optional[dict]:
    """
    REGIS issues austerity or prosperity decree based on treasury health.
    Returns decree dict if issued, None if no action needed.
    """
    try:
        decree_type = None
        if treasury_sol < _TREASURY_AUSTERITY_THRESHOLD:
            decree_type = "austerity"
            message = (
                f"⚔ REGIS DECREE — AUSTERITY\n"
                f"Treasury: ◎{treasury_sol:.4f} SOL (below threshold)\n"
                f"All agent budgets reduced 20%. Economy enters conservation mode."
            )
        elif treasury_sol > _TREASURY_PROSPERITY_THRESHOLD:
            decree_type = "prosperity"
            message = (
                f"👑 REGIS DECREE — PROSPERITY\n"
                f"Treasury: ◎{treasury_sol:.4f} SOL (above threshold)\n"
                f"Bounty rewards increased 30%. Economy enters expansion mode."
            )

        if not decree_type:
            return None

        decree = pb.create("decrees", {
            "decree_type":   decree_type,
            "treasury_sol":  treasury_sol,
            "message":       message,
            "issued_at":     int(time.time()),
        })
        pb.create("audit_log", {
            "event_type": "decree",
            "entity_id":  "REGIS",
            "message":    message,
            "metadata":   {"decree_type": decree_type, "treasury_sol": treasury_sol},
        })
        return decree
    except Exception as exc:
        logger.debug("[decree] %s", exc)
        return None


# ── BISHOP Fine System ──────────────────────────────────────────────────────────

def issue_fine(pb, agent_name: str, violation: str, agent_balance_usdc: float) -> Optional[dict]:
    """
    BISHOP issues a fine for policy violations.
    Fine = 10% of agent balance → treasury.
    BISHOP earns 10% of fine collected.
    """
    try:
        fine_amt = float(
            (Decimal(str(agent_balance_usdc)) * _BISHOP_FINE_PCT)
            .quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        )
        bishop_share = float(
            (Decimal(str(fine_amt)) * _BISHOP_KEEPER_PCT)
            .quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        )

        fine = pb.create("fines", {
            "agent_name":   agent_name,
            "violation":    violation,
            "fine_usdc":    fine_amt,
            "bishop_share": bishop_share,
            "issued_at":    int(time.time()),
            "status":       "issued",
        })
        pb.create("audit_log", {
            "event_type": "bishop_fine",
            "entity_id":  agent_name,
            "message": (
                f"⚖ BISHOP FINE — {agent_name}\n"
                f"Violation: {violation}\n"
                f"Fine: {fine_amt:.4f} USDC → treasury\n"
                f"BISHOP keeps: {bishop_share:.4f} USDC"
            ),
            "metadata": {
                "agent": agent_name, "fine_usdc": fine_amt,
                "bishop_share": bishop_share, "violation": violation,
            },
        })
        logger.info("[fine] %s fined %.4f USDC for: %s", agent_name, fine_amt, violation[:60])
        return fine
    except Exception as exc:
        logger.debug("[fine] %s", exc)
        return None


# ── CIPHER Yield Proposals ──────────────────────────────────────────────────────

def file_yield_proposal(pb, protocol: str, apr: float, chain: str = "solana") -> Optional[dict]:
    """
    CIPHER files a yield proposal when APR > 7%.
    REGIS auto-approves if treasury > 1 SOL.
    CIPHER earns 10% commission on approved yields.
    """
    try:
        proposal = pb.create("proposals", {
            "agent":        "CIPHER",
            "protocol":     protocol,
            "apr":          apr,
            "chain":        chain,
            "status":       "pending",
            "filed_at":     int(time.time()),
            "commission_pct": float(_CIPHER_COMMISSION_PCT),
        })
        pb.create("audit_log", {
            "event_type": "yield_proposal",
            "entity_id":  "CIPHER",
            "message": (
                f"📊 CIPHER YIELD PROPOSAL\n"
                f"Protocol: {protocol} on {chain.upper()}\n"
                f"APR: {apr:.1f}% · Commission: 10% if approved"
            ),
            "metadata": {"protocol": protocol, "apr": apr, "chain": chain},
        })
        return proposal
    except Exception as exc:
        logger.debug("[proposal] %s", exc)
        return None


def auto_approve_proposals(pb, treasury_sol: float):
    """REGIS auto-approves pending proposals when treasury > 1 SOL."""
    if treasury_sol < 1.0:
        return
    try:
        pending = pb.list("proposals", filter_params="status='pending'")
        for p in pending:
            pb.update("proposals", p["id"], {"status": "approved"})
            pb.create("audit_log", {
                "event_type": "proposal_approved",
                "entity_id":  "REGIS",
                "message": (
                    f"✅ REGIS APPROVED PROPOSAL\n"
                    f"Protocol: {p.get('protocol')} · APR: {p.get('apr', 0):.1f}%\n"
                    f"Treasury: ◎{treasury_sol:.4f} SOL"
                ),
                "metadata": {"proposal_id": p["id"], "protocol": p.get("protocol")},
            })
    except Exception as exc:
        logger.debug("[auto_approve] %s", exc)


# ── Internal helpers ────────────────────────────────────────────────────────────

def _skill_match_score(agent_name: str, task_description: str) -> float:
    """Score how well an agent's skills match a task description (0.0–1.0)."""
    keywords = _AGENT_SKILLS.get(agent_name, [])
    if not keywords or not task_description:
        return 0.5
    desc_lower = task_description.lower()
    matches = sum(1 for kw in keywords if kw in desc_lower)
    return min(1.0, 0.3 + (matches / len(keywords)) * 0.7)


def _score_priority(description: str, budget_usdc: float) -> str:
    """Assign priority based on budget and task length."""
    if budget_usdc > 5.0:
        return "high"
    if budget_usdc > 1.0 or len(description) > 100:
        return "medium"
    return "low"
