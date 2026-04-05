"""
BISHOP Email Service — governance-grade notifications via Resend.

Design contract:
  • Email is reserved for governance moments, not routine events
  • Telegram handles high-frequency operational updates
  • All functions are synchronous (called via asyncio.to_thread in async context)
  • All failures are logged and swallowed — email must never break task execution
  • Amounts are passed in SOL (converted by caller from USDC using rate)

Four triggers:
  1. send_critical_block   — payment blocked above 0.1 SOL threshold
  2. send_treasury_low     — treasury drops below configurable threshold
  3. send_task_receipt     — full P&L receipt on task completion
  4. send_punishment_record — REGIS governance penalty applied
"""

import logging
import os

logger = logging.getLogger("swarmpay.email")

# ── Configuration ──────────────────────────────────────────────────────────────

ENABLED = os.environ.get("BISHOP_EMAILS_ENABLED", "").lower() in ("true", "1", "yes")
FROM    = "BISHOP <onboarding@resend.dev>"
TO      = os.environ.get("BISHOP_EMAIL_TO", "")

# Treasury alert threshold (SOL) — configurable, default 0.1 SOL
TREASURY_LOW_THRESHOLD_SOL = float(os.environ.get("TREASURY_LOW_THRESHOLD_SOL", "0.1"))

# Critical block threshold (SOL) — only email when blocked amount exceeds this
CRITICAL_BLOCK_THRESHOLD_SOL = float(os.environ.get("CRITICAL_BLOCK_THRESHOLD_SOL", "0.1"))

# ── HTML Base Styles ───────────────────────────────────────────────────────────

_BASE_STYLE = """
body {
  font-family: 'Courier New', monospace;
  background: #0a0a0a;
  color: #e5e5e5;
  padding: 30px;
  max-width: 580px;
  margin: 0 auto;
}
.seal {
  text-align: center;
  color: #F59E0B;
  border: 1px solid #F59E0B;
  padding: 16px;
  letter-spacing: 0.3em;
  margin-bottom: 24px;
}
.divider {
  border-top: 1px solid #222;
  margin: 16px 0;
}
.label {
  color: #666;
  font-size: 11px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
}
.sol   { color: #9945FF; }
.green { color: #22C55E; }
.red   { color: #EF4444; }
.gold  { color: #F59E0B; }
.footer {
  color: #444;
  font-size: 11px;
  margin-top: 24px;
  font-style: italic;
}
"""

_SEAL = """
<div class="seal">
  ⛪ SWARMPAY BISHOPRIC<br/>
  <small style="font-size:10px">Office of Compliance &amp; Treasury</small>
</div>
"""


def _send(subject: str, html: str) -> None:
    """
    Core send function. All failures are logged and swallowed.
    Never raises — email must not block task execution.
    """
    if not ENABLED or not TO:
        return
    try:
        import resend
        resend.api_key = os.environ.get("RESEND_API_KEY", "")
        if not resend.api_key:
            logger.warning("[bishop email] RESEND_API_KEY not set — skipping email")
            return
        resend.Emails.send({
            "from": FROM,
            "to": [TO],
            "subject": subject,
            "html": f"""<!DOCTYPE html>
<html>
<head><style>{_BASE_STYLE}</style></head>
<body>{_SEAL}{html}</body>
</html>""",
        })
        logger.info("[bishop email] sent: %s", subject)
    except Exception as exc:
        logger.warning("[bishop email] failed: %s", exc)


# ── Trigger 1 — Critical Block ─────────────────────────────────────────────────

def send_critical_block(
    agent: str,
    amount_sol: float,
    reason: str,
    task_description: str,
) -> None:
    """
    Fire when a payment is blocked and the blocked amount exceeds
    CRITICAL_BLOCK_THRESHOLD_SOL. Signals a governance intervention.
    """
    if amount_sol <= CRITICAL_BLOCK_THRESHOLD_SOL:
        return
    _send(
        subject=f"\U0001f6a8 CRITICAL BLOCK — {agent} \u25ce{amount_sol:.3f} SOL",
        html=f"""
        <p class="label">Policy Violation</p>
        <p>Agent <span class="gold">{agent}</span>
        attempted <span class="red">\u25ce{amount_sol:.3f} SOL</span> and was blocked.</p>
        <p><strong>Reason:</strong> {reason}</p>
        <p><strong>Task:</strong> {task_description[:120]}</p>
        <div class="divider"></div>
        <p class="footer">
        Blocked amount saved from treasury disbursement.<br/>
        — BISHOP, Chief Compliance Officer
        </p>
        """,
    )


# ── Trigger 2 — Treasury Low ───────────────────────────────────────────────────

def send_treasury_low(
    balance_sol: float,
    threshold_sol: float,
) -> None:
    """
    Fire when REGIS treasury balance drops below threshold after task settlement.
    """
    _send(
        subject=f"\u26a0\ufe0f TREASURY LOW — \u25ce{balance_sol:.3f} SOL remaining",
        html=f"""
        <p class="label">Treasury Alert</p>
        <p>REGIS treasury has dropped below
        <span class="gold">\u25ce{threshold_sol:.2f} SOL</span>.</p>
        <p>Current balance:
        <span class="red">\u25ce{balance_sol:.3f} SOL</span></p>
        <p>Top up via MoonPay to continue operations.
        Operations in dry-run mode until replenished.</p>
        <div class="divider"></div>
        <p class="footer">— BISHOP, Chief Compliance Officer</p>
        """,
    )


# ── Trigger 3 — Task Complete Receipt ─────────────────────────────────────────

def send_task_receipt(
    task_description: str,
    signed_count: int,
    blocked_count: int,
    distributed_sol: float,
    saved_sol: float,
    remaining_sol: float,
    solana_tx_hashes: list,
) -> None:
    """
    Full P&L governance receipt on task completion.
    Fired once per task — the authoritative settlement record.
    """
    tx_links_html = ""
    for tx in solana_tx_hashes:
        if tx:
            tx_links_html += (
                f'<p><a href="https://solscan.io/tx/{tx}?cluster=devnet" '
                f'style="color:#9945FF">{tx[:24]}…</a></p>'
            )
    if not tx_links_html:
        tx_links_html = '<p style="color:#444">Dry-run mode — no on-chain transactions</p>'

    _send(
        subject=f"\u26ea DECREE — Task Complete: {task_description[:50]}",
        html=f"""
        <p class="label">Task Complete</p>
        <p>{task_description[:200]}</p>
        <div class="divider"></div>
        <p class="label">Settlements</p>
        <p>
          <span class="green">\u2713 Signed: {signed_count}</span> &nbsp;&middot;&nbsp;
          <span class="red">\u2717 Blocked: {blocked_count}</span>
        </p>
        <p>Distributed: <span class="sol">\u25ce{distributed_sol:.4f} SOL</span></p>
        <p>Policy saved: <span class="green">\u25ce{saved_sol:.4f} SOL</span></p>
        <p>Treasury remaining: <span class="sol">\u25ce{remaining_sol:.4f} SOL</span></p>
        <div class="divider"></div>
        <p class="label">Solana Transactions</p>
        {tx_links_html}
        <div class="divider"></div>
        <p class="footer">
        Opus completum est. Deo gratias.<br/>
        — BISHOP, Chief Compliance Officer
        </p>
        """,
    )


# ── Trigger 4 — REGIS Punishment Record ───────────────────────────────────────

def send_overthrow_email(old_ruler: dict, new_ruler: dict) -> None:
    """
    Succession event email. Fired once per overthrow.
    old_ruler and new_ruler are dicts with keys:
      name, city, lifetime_distributed (old) / lifetime_earnings (new),
      overthrow_count, times_ruled.
    """
    old_name = old_ruler.get("name", "?")
    new_name = new_ruler.get("name", "?")
    new_city = new_ruler.get("city", "")
    new_earn = float(new_ruler.get("lifetime_earnings", 0))
    old_dist = float(old_ruler.get("lifetime_distributed", 0))
    margin   = new_earn - old_dist

    # Convert USDC → SOL for display (fallback rate, governance display only)
    _rate = 79.0
    new_earn_sol = new_earn / _rate
    old_dist_sol = old_dist / _rate
    margin_sol   = margin   / _rate

    succession_n = int(old_ruler.get("overthrow_count", 0)) + 1

    _send(
        subject=f"\u2694\ufe0f OVERTHROW \u2014 {new_name} seizes the throne",
        html=f"""
        <div class="seal" style="color:#9945FF; border-color:#9945FF">
          \u2694\ufe0f SUCCESSION EVENT<br/>
          <small>Kingdom of SwarmPay</small>
        </div>

        <p class="label">The Throne Has Changed Hands</p>
        <p>
          <span style="color:#9945FF">{new_name} ({new_city})</span>
          has overthrown
          <span style="color:#F59E0B">{old_name}</span>
          through superior economic performance.
        </p>

        <div class="divider"></div>

        <p class="label">The Numbers</p>
        <table style="width:100%; border-collapse:collapse; font-family:monospace; font-size:12px;">
          <tr>
            <td style="padding:4px 0; color:#888;">{new_name} earned:</td>
            <td style="color:#9945FF; text-align:right;">
              \u25ce{new_earn_sol:.4f} SOL
              <span style="color:#555; font-size:10px;">({new_earn:.4f} USDC)</span>
            </td>
          </tr>
          <tr>
            <td style="padding:4px 0; color:#888;">{old_name} distributed:</td>
            <td style="color:#F59E0B; text-align:right;">
              \u25ce{old_dist_sol:.4f} SOL
              <span style="color:#555; font-size:10px;">({old_dist:.4f} USDC)</span>
            </td>
          </tr>
          <tr>
            <td style="padding:4px 0; color:#888;">Margin of victory:</td>
            <td style="color:#22C55E; text-align:right;">
              \u25ce{margin_sol:.4f} SOL
              <span style="color:#555; font-size:10px;">({margin:.4f} USDC)</span>
            </td>
          </tr>
        </table>

        <div class="divider"></div>

        <p class="label">Succession Record</p>
        <p>
          {old_name}: <span style="color:#666">The Deposed</span><br/>
          Overthrown: {succession_n} time(s)<br/>
          Times ruled: {int(old_ruler.get("times_ruled", 0))}
        </p>
        <p>
          {new_name}: <span style="color:#9945FF">The New Sovereign</span><br/>
          Times ruled: {int(new_ruler.get("times_ruled", 0)) + 1}
        </p>

        <div class="divider"></div>

        <p class="footer">
          The kingdom is governed by performance, not birthright. Merit is sovereign.<br/><br/>
          \u2014 BISHOP<br/>
          Chief Compliance Officer<br/>
          Witnessing succession #{succession_n}
        </p>
        """,
    )


def send_punishment_record(
    punishment_type: str,
    audit_score: int,
    regis_response: str,
) -> None:
    """
    Governance record when REGIS is formally punished.
    audit_score=0 means punishment was applied without a preceding audit.
    """
    score_display = f"{audit_score}/100" if audit_score > 0 else "manually applied"
    _send(
        subject=f"\u2694\ufe0f REGIS PENALIZED — {punishment_type.replace('_', ' ').upper()}",
        html=f"""
        <p class="label">Governance Action</p>
        <p>Audit Score: <span class="red">{score_display}</span></p>
        <p>Punishment: <span class="gold">{punishment_type.replace("_", " ").upper()}</span></p>
        <div class="divider"></div>
        <p class="label">REGIS Responds</p>
        <p style="font-style: italic; color: #999;">&ldquo;{regis_response}&rdquo;</p>
        <div class="divider"></div>
        <p class="footer">
        This record has been appended to the sovereign brain.<br/>
        — BISHOP, Chief Compliance Officer
        </p>
        """,
    )
