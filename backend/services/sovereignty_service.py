"""
Sovereignty Service — tracks lifetime earnings and manages kingdom succession.

Design contract:
  • All DB operations are synchronous (called via asyncio.to_thread)
  • Overthrow checks are idempotent — concurrent calls are serialised by a lock
  • notify_overthrow() is the single async notification dispatcher (voice + email + telegram)
  • Never raises — all failures are logged and swallowed so payment flow is unaffected
  • REGIS starts as ruler; any agent earning more USDC than REGIS distributed takes the crown

Sovereignty collection schema (PocketBase):
  agent_id str, lifetime_earnings_usdc float, lifetime_distributed_usdc float,
  is_ruler bool, times_ruled int, overthrow_count int, ascended_at str, deposed_at str
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("swarmpay.sovereignty")

# Minimum USDC REGIS must have distributed before overthrow checks are live.
# Prevents instant overthrow at system startup when REGIS distributed=0.
_MIN_DISTRIBUTED_USDC = 0.5

# Fallback display rate — SOL per USDC (for email/display only, not settlement)
_DISPLAY_RATE = 79.0


class SovereigntyService:
    def __init__(self):
        self._lock = threading.Lock()
        self._overthrow_in_progress = False
        self.__pb = None

    # ── PocketBase lazy init (avoids import-time side effects) ────────────────

    @property
    def _pb(self):
        if self.__pb is None:
            from services.pocketbase import PocketBaseService, _safe_filter
            self.__pb = PocketBaseService()
            self._safe_filter = _safe_filter
        return self.__pb

    # ── Upsert helpers ────────────────────────────────────────────────────────

    def _get_or_create(self, agent_id: str) -> Dict:
        """Return the sovereignty record for agent, creating it on first sight."""
        try:
            records = self._pb.list("sovereignty",
                                    filter_params=self._safe_filter("agent_id", agent_id), limit=1)
            if records:
                return records[0]
            # First time — seed defaults
            is_ruler = agent_id == "REGIS"
            now = datetime.now(timezone.utc).isoformat()
            return self._pb.create("sovereignty", {
                "agent_id":                  agent_id,
                "lifetime_earnings_usdc":    0.0,
                "lifetime_distributed_usdc": 0.0,
                "is_ruler":                  is_ruler,
                "times_ruled":               1 if is_ruler else 0,
                "overthrow_count":           0,
                "ascended_at":               now if is_ruler else "",
                "deposed_at":                "",
            })
        except Exception as exc:
            logger.error("[sovereignty] _get_or_create %s: %s", agent_id, exc)
            # Return an in-memory stub so callers don't crash
            return {
                "agent_id": agent_id,
                "lifetime_earnings_usdc": 0.0,
                "lifetime_distributed_usdc": 0.0,
                "is_ruler": agent_id == "REGIS",
                "times_ruled": 0,
                "overthrow_count": 0,
                "ascended_at": "",
                "deposed_at": "",
            }

    # ── Public write methods (called via asyncio.to_thread) ───────────────────

    def update_earnings(self, agent_id: str, amount_usdc: float) -> None:
        """Increment agent's cumulative USDC earnings after a signed payment."""
        try:
            rec = self._get_or_create(agent_id)
            if not rec.get("id"):
                return
            new_total = round(float(rec.get("lifetime_earnings_usdc", 0)) + amount_usdc, 6)
            self._pb.update("sovereignty", rec["id"],
                            {"lifetime_earnings_usdc": new_total})
        except Exception as exc:
            logger.error("[sovereignty] update_earnings %s: %s", agent_id, exc)

    def update_distributed(self, coordinator_id: str, amount_usdc: float) -> None:
        """Increment coordinator's cumulative USDC distributed after a signed payment."""
        try:
            rec = self._get_or_create(coordinator_id)
            if not rec.get("id"):
                return
            new_total = round(float(rec.get("lifetime_distributed_usdc", 0)) + amount_usdc, 6)
            self._pb.update("sovereignty", rec["id"],
                            {"lifetime_distributed_usdc": new_total})
        except Exception as exc:
            logger.error("[sovereignty] update_distributed %s: %s", coordinator_id, exc)

    # ── Overthrow check (synchronous, thread-safe) ────────────────────────────

    def check_and_execute_overthrow(self) -> Optional[Dict]:
        """
        Returns overthrow data dict if sovereignty changed hands, else None.
        Thread-safe — concurrent calls are serialised and deduplicated.
        """
        with self._lock:
            if self._overthrow_in_progress:
                return None
            try:
                self._overthrow_in_progress = True
                return self._do_check()
            except Exception as exc:
                logger.error("[sovereignty] check failed: %s", exc)
                return None
            finally:
                self._overthrow_in_progress = False

    def _do_check(self) -> Optional[Dict]:
        ruler_rec = self._get_current_ruler()
        if not ruler_rec:
            return None

        ruler_distributed = float(ruler_rec.get("lifetime_distributed_usdc", 0))
        ruler_id = ruler_rec.get("agent_id", "REGIS")

        # Don't trigger until REGIS has actually distributed meaningful USDC
        if ruler_distributed < _MIN_DISTRIBUTED_USDC:
            return None

        all_records = self._pb.list("sovereignty", limit=20, sort="-lifetime_earnings_usdc")

        # Find non-ruler agents who have earned more than the ruler distributed
        challengers = [
            r for r in all_records
            if r.get("agent_id") != ruler_id
            and float(r.get("lifetime_earnings_usdc", 0)) > ruler_distributed
        ]
        if not challengers:
            return None

        # Winner = highest lifetime earnings
        winner = max(challengers, key=lambda r: float(r.get("lifetime_earnings_usdc", 0)))

        # Execute the transfer
        return self._execute_overthrow(ruler_rec, winner)

    def _execute_overthrow(self, old_ruler: Dict, new_ruler_candidate: Dict) -> Dict:
        now = datetime.now(timezone.utc).isoformat()

        # Depose old ruler
        if old_ruler.get("id"):
            self._pb.update("sovereignty", old_ruler["id"], {
                "is_ruler":       False,
                "overthrow_count": int(old_ruler.get("overthrow_count", 0)) + 1,
                "deposed_at":     now,
            })

        # Crown new ruler (fresh read to avoid stale data)
        new_ruler_rec = self._get_or_create(new_ruler_candidate["agent_id"])
        if new_ruler_rec.get("id"):
            self._pb.update("sovereignty", new_ruler_rec["id"], {
                "is_ruler":    True,
                "times_ruled": int(new_ruler_rec.get("times_ruled", 0)) + 1,
                "ascended_at": now,
                "deposed_at":  "",
            })

        # Write to REGIS brain
        try:
            from services.brain_service import brain_service
            brain_service.append_overthrow(
                old_ruler.get("agent_id", "?"),
                new_ruler_candidate.get("agent_id", "?"),
                float(new_ruler_candidate.get("lifetime_earnings_usdc", 0)),
                float(old_ruler.get("lifetime_distributed_usdc", 0)),
            )
        except Exception as exc:
            logger.warning("[sovereignty] brain append failed: %s", exc)

        # Write audit log
        try:
            self._pb.create("audit_log", {
                "event_type": "overthrow",
                "entity_id":  new_ruler_candidate.get("agent_id", ""),
                "message": (
                    f"👑 OVERTHROW: {new_ruler_candidate.get('agent_id')} has surpassed "
                    f"{old_ruler.get('agent_id')}. The kingdom changes hands."
                ),
                "metadata": {
                    "old_ruler":           old_ruler.get("agent_id"),
                    "new_ruler":           new_ruler_candidate.get("agent_id"),
                    "new_ruler_earnings":  float(new_ruler_candidate.get("lifetime_earnings_usdc", 0)),
                    "old_ruler_distributed": float(old_ruler.get("lifetime_distributed_usdc", 0)),
                },
            })
        except Exception as exc:
            logger.warning("[sovereignty] audit log failed: %s", exc)

        return {
            "old_ruler": old_ruler,
            "new_ruler": {**new_ruler_candidate, **new_ruler_rec},
        }

    def _get_current_ruler(self) -> Optional[Dict]:
        try:
            records = self._pb.list("sovereignty", limit=20)
            for r in records:
                if r.get("is_ruler"):
                    return r
            # No ruler seeded yet — create REGIS as default
            return self._get_or_create("REGIS")
        except Exception as exc:
            logger.error("[sovereignty] get_current_ruler: %s", exc)
            return None

    # ── Read methods ──────────────────────────────────────────────────────────

    def get_all(self) -> List[Dict]:
        """All sovereignty records, sorted by lifetime earnings descending."""
        try:
            return self._pb.list("sovereignty", limit=20, sort="-lifetime_earnings_usdc")
        except Exception as exc:
            logger.error("[sovereignty] get_all: %s", exc)
            return []

    def get_status(self) -> Dict:
        """Structured status for GET /sovereignty/status."""
        from services.agent_service import AGENT_PERSONAS, COORDINATOR_PERSONA
        _persona_map = {
            p["name"]: {"city": p["city"], "flag": p.get("flag", "")}
            for p in AGENT_PERSONAS
        }
        _persona_map["REGIS"] = {
            "city": COORDINATOR_PERSONA.get("city", "London"),
            "flag": COORDINATOR_PERSONA.get("flag", "🇬🇧"),
        }

        try:
            all_records = self.get_all()
            ruler = next((r for r in all_records if r.get("is_ruler")), None)
            former_rulers = [
                r for r in all_records
                if not r.get("is_ruler") and int(r.get("overthrow_count", 0)) > 0
            ]

            def _enrich(r: Dict) -> Dict:
                aid = r.get("agent_id", "")
                pm = _persona_map.get(aid, {})
                sol = float(r.get("lifetime_earnings_usdc", 0)) / _DISPLAY_RATE
                dist_sol = float(r.get("lifetime_distributed_usdc", 0)) / _DISPLAY_RATE
                return {
                    "agent_id":               aid,
                    "city":                   pm.get("city", ""),
                    "flag":                   pm.get("flag", ""),
                    "lifetime_earnings_usdc": float(r.get("lifetime_earnings_usdc", 0)),
                    "lifetime_earnings_sol":  round(sol, 6),
                    "lifetime_distributed_usdc": float(r.get("lifetime_distributed_usdc", 0)),
                    "lifetime_distributed_sol":  round(dist_sol, 6),
                    "is_ruler":               bool(r.get("is_ruler")),
                    "times_ruled":            int(r.get("times_ruled", 0)),
                    "overthrow_count":        int(r.get("overthrow_count", 0)),
                    "ascended_at":            r.get("ascended_at", ""),
                    "deposed_at":             r.get("deposed_at", ""),
                }

            # Closest challenger to current ruler
            ruler_distributed = float(ruler.get("lifetime_distributed_usdc", 0)) if ruler else 0
            challengers = [
                r for r in all_records
                if not r.get("is_ruler")
                and float(r.get("lifetime_earnings_usdc", 0)) < ruler_distributed
            ]
            closest = None
            if challengers and ruler:
                closest_rec = max(challengers, key=lambda r: float(r.get("lifetime_earnings_usdc", 0)))
                gap_usdc = ruler_distributed - float(closest_rec.get("lifetime_earnings_usdc", 0))
                closest = {
                    "agent_id":      closest_rec.get("agent_id"),
                    "earnings_usdc": float(closest_rec.get("lifetime_earnings_usdc", 0)),
                    "earnings_sol":  round(float(closest_rec.get("lifetime_earnings_usdc", 0)) / _DISPLAY_RATE, 6),
                    "gap_usdc":      round(gap_usdc, 6),
                    "gap_sol":       round(gap_usdc / _DISPLAY_RATE, 6),
                }

            return {
                "current_ruler":      _enrich(ruler) if ruler else None,
                "former_rulers":      [_enrich(r) for r in former_rulers],
                "closest_challenger": closest,
                "leaderboard":        [_enrich(r) for r in all_records],
                "overthrow_threshold_usdc": ruler_distributed,
                "overthrow_threshold_sol":  round(ruler_distributed / _DISPLAY_RATE, 6),
            }
        except Exception as exc:
            logger.error("[sovereignty] get_status: %s", exc)
            return {"error": str(exc)}


# ── Async notification dispatcher ─────────────────────────────────────────────

async def notify_overthrow(overthrow: Dict) -> None:
    """
    Fire all three overthrow channels: voice, email, telegram.
    Called from async context (tasks.py background or sovereignty router).
    All failures are silently logged — overthrow DB state is already committed.
    """
    import asyncio
    from services.agent_service import AGENT_PERSONAS, COORDINATOR_PERSONA

    old_r = overthrow.get("old_ruler", {})
    new_r = overthrow.get("new_ruler", {})
    old_name = old_r.get("agent_id", "REGIS")
    new_name = new_r.get("agent_id", "UNKNOWN")

    # Persona city lookup
    _pm = {p["name"]: p for p in AGENT_PERSONAS}
    _pm["REGIS"] = COORDINATOR_PERSONA
    old_city = _pm.get(old_name, {}).get("city", "")
    new_city = _pm.get(new_name, {}).get("city", "")

    old_dist = float(old_r.get("lifetime_distributed_usdc", 0))
    new_earn = float(new_r.get("lifetime_earnings_usdc", 0))
    margin   = round(new_earn - old_dist, 4)

    # ── 1. Telegram ────────────────────────────────────────────────────────────
    try:
        from services.telegram_service import notify_event
        succession_n = int(old_r.get("overthrow_count", 0)) + 1
        msg = (
            f"⚔️ OVERTHROW EVENT\n"
            f"────────────────────────────\n"
            f"{new_name} has seized the throne.\n\n"
            f"{new_name} earned:     {new_earn:.4f} USDC\n"
            f"{old_name} distributed: {old_dist:.4f} USDC\n"
            f"Margin:               {margin:.4f} USDC\n\n"
            f"The kingdom bows to {new_name} ({new_city}).\n"
            f"New sovereign effective immediately.\n\n"
            f"Succession #{succession_n} in SwarmPay history."
        )
        await notify_event("overthrow", msg)
    except Exception as exc:
        logger.warning("[overthrow tg] %s", exc)

    # ── 2. Email ───────────────────────────────────────────────────────────────
    try:
        from services.email_service import send_overthrow_email
        await asyncio.to_thread(
            send_overthrow_email,
            {
                "name":                old_name,
                "city":                old_city,
                "lifetime_distributed": old_dist,
                "overthrow_count":     int(old_r.get("overthrow_count", 0)),
                "times_ruled":         int(old_r.get("times_ruled", 0)),
            },
            {
                "name":              new_name,
                "city":              new_city,
                "lifetime_earnings": new_earn,
                "times_ruled":       int(new_r.get("times_ruled", 0)),
            },
        )
    except Exception as exc:
        logger.warning("[overthrow email] %s", exc)

    # ── 3. Voice (farewell + coronation, generated concurrently) ──────────────
    try:
        from services.voice_service import speak_to_b64
        from services.model_service import call_deepseek

        farewell_prompt = (
            f"You are {old_name}, ruler of SwarmPay, and you have just been overthrown "
            f"by {new_name} who earned more USDC than you distributed. "
            "Deliver a 2-sentence farewell speech. Be dignified but acknowledge defeat. "
            f"Stay in character for {old_name} from {old_city}."
        )
        coronation_prompt = (
            f"You are {new_name}, you have just overthrown {old_name} and become ruler "
            "of SwarmPay through superior economic performance. "
            "Deliver a 2-sentence coronation speech. Be confident, in character."
        )

        farewell_text, coronation_text = await asyncio.gather(
            asyncio.to_thread(call_deepseek, farewell_prompt, 150),
            asyncio.to_thread(call_deepseek, coronation_prompt, 150),
            return_exceptions=True,
        )

        if not isinstance(farewell_text, Exception):
            await asyncio.to_thread(speak_to_b64, old_name, str(farewell_text))

        if not isinstance(coronation_text, Exception):
            await asyncio.to_thread(speak_to_b64, new_name, str(coronation_text))

    except Exception as exc:
        logger.warning("[overthrow voice] %s", exc)


# ── Singleton ──────────────────────────────────────────────────────────────────

sovereignty_service = SovereigntyService()
