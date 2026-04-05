"""
Brain Service — Thread-safe persistent memory for REGIS.
Append-only log model: every state change creates a timestamped entry.
The LLM reads the full file as rolling context.
"""

import os
import threading
from datetime import datetime, timezone
from typing import Dict, List, Any

_BRAIN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "regis_brain.md")
_LOCK = threading.Lock()


class BrainService:
    def __init__(self, path: str = _BRAIN_PATH):
        self.path = os.path.abspath(path)
        if not os.path.exists(self.path):
            self._initialize()

    def _initialize(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        # Copy seed from the static file if it exists, else write minimal template
        seed_path = os.path.join(os.path.dirname(self.path), "regis_brain.md")
        if os.path.exists(seed_path) and seed_path != self.path:
            with open(seed_path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = "# REGIS SOVEREIGN BRAIN\n## Event Log\n"
        with _LOCK:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(content)

    def read(self) -> str:
        with _LOCK:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return f.read()
            except FileNotFoundError:
                self._initialize()
                return "# REGIS SOVEREIGN BRAIN\n## Event Log\n"

    def append(self, section: str, content: str):
        """Append a single timestamped line to the Event Log. Never raises."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        line = f"[{now}] [{section}] {content}\n"
        try:
            with _LOCK:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line)
        except OSError as exc:
            import logging
            logging.getLogger("swarmpay.brain").error(
                "Brain write failed (section=%s): %s", section, exc
            )

    # ── High-level update helpers ─────────────────────────────────────

    def update_after_task(self, task: Dict, sub_tasks: List[Dict], payments: List[Dict]):
        signed  = [p for p in payments if p.get("status") == "signed"
                   and not (p.get("policy_reason", "") or "").startswith("PEER:")]
        blocked = [p for p in payments if p.get("status") == "blocked"]
        peers   = [p for p in payments if (p.get("policy_reason", "") or "").startswith("PEER:")]
        total   = sum(float(p.get("amount", 0)) for p in signed)

        summary = (
            f"Task '{task.get('description', '')[:50]}' complete. "
            f"Paid {len(signed)} agent(s) {total:.4f} USDC total. "
        )
        for p in blocked:
            st = next((s for s in sub_tasks if s.get("wallet_id") == p.get("to_wallet_id")), {})
            agent = st.get("agent_id", "AGENT")
            reason = (p.get("policy_reason") or "policy")[:80]
            summary += f"BLOCKED {agent}: {reason}. "
        if peers:
            summary += f"Peer payments: {len(peers)} transfers."
        self.append("TASK_COMPLETE", summary)

    def append_probe(self, question: str, answer: str):
        self.append("PROBE_Q", question[:120])
        self.append("PROBE_A", answer[:220])

    def append_audit(self, score: int, verdict: str, reason: str, rep_delta: float):
        status = "REPUTATION_UP" if rep_delta > 0 else ("REPUTATION_DOWN" if rep_delta < 0 else "NO_CHANGE")
        self.append("AUDIT", f"{verdict} score={score}/100 rep_delta={rep_delta:+.1f} [{status}] reason={reason[:100]}")

    def append_punishment(self, punishment_type: str, regis_response: str):
        self.append("PUNISHMENT_RECEIVED", f"type={punishment_type} response={regis_response[:180]}")


# Singleton — imported by both regis.py router and tasks.py
brain_service = BrainService()
