"""
Cache Service — Simple In-Memory Semantic Caching.

Reduces redundant API calls for duplicate queries (e.g. repeated demo searches)
by caching outputs securely in memory. Uses simple dict with Time-To-Live.
"""

import time
import hashlib
import logging
from typing import Any, Optional

logger = logging.getLogger("swarmpay.cache")

_cache: dict[str, dict[str, Any]] = {}
DEFAULT_TTL = 300  # 5 minutes


def _hash_key(namespace: str, query: str) -> str:
    """Generate a stable hash for a given query string."""
    clean_query = str(query).strip().lower()
    return f"{namespace}:{hashlib.sha256(clean_query.encode()).hexdigest()}"


def get_cached(namespace: str, query: str) -> Optional[Any]:
    """Retrieve item if it exists and hasn't expired."""
    key = _hash_key(namespace, query)
    entry = _cache.get(key)
    if entry:
        if time.time() - entry["ts"] < entry["ttl"]:
            logger.debug(f"[cache hit] {namespace} (saved API call)")
            return entry["data"]
        else:
            del _cache[key]
    return None


def set_cached(namespace: str, query: str, data: Any, ttl: int = DEFAULT_TTL) -> None:
    """Store an item in the cache with a TTL."""
    if not data:
        return
    key = _hash_key(namespace, query)
    _cache[key] = {
        "data": data,
        "ts": time.time(),
        "ttl": ttl
    }
