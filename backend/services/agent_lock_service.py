"""
Agent Lock Service — pause/resume individual agents.

Locked agents are skipped during task analysis and spawning.
State is in-memory (resets on restart) and optionally logged to brain.
Telegram commands: /lock ATLAS, /unlock ATLAS, /locked
"""

import os
from typing import Set, Dict

# In-memory lock state (fast, no DB round-trip)
_locked: Set[str] = set()

# Optional reason tracking
_lock_reasons: Dict[str, str] = {}

VALID_AGENTS = {"ATLAS", "CIPHER", "FORGE", "BISHOP", "SØN"}


def lock_agent(name: str, reason: str = "Locked via Telegram") -> bool:
    """Lock an agent. Returns True if newly locked, False if already locked."""
    name = name.upper()
    if name not in VALID_AGENTS:
        return False
    was_locked = name in _locked
    _locked.add(name)
    _lock_reasons[name] = reason
    return not was_locked


def unlock_agent(name: str) -> bool:
    """Unlock an agent. Returns True if was locked, False if already free."""
    name = name.upper()
    was_locked = name in _locked
    _locked.discard(name)
    _lock_reasons.pop(name, None)
    return was_locked


def is_locked(name: str) -> bool:
    return name.upper() in _locked


def get_locked() -> Dict[str, str]:
    """Return dict of {agent_name: reason} for all locked agents."""
    return {name: _lock_reasons.get(name, "No reason given") for name in _locked}


def filter_available(agent_names: list) -> list:
    """Return only the agents not currently locked."""
    return [a for a in agent_names if not is_locked(a)]
