"""
Analytics Router — Token economy endpoints.
  GET /analytics/tokens?task_id=<id>  — session token usage summary
"""

from fastapi import APIRouter, Query
from services.model_service import get_session_summary

router = APIRouter(prefix="/analytics", tags=["analytics"])

_FALLBACK_SOL_USDC_RATE = 79.0  # fallback only


@router.get("/tokens")
async def get_token_usage(task_id: str = Query(default="")):
    """Return aggregated token usage for a task session."""
    if not task_id:
        return {
            "total_tokens": 0, "total_cost_usd": 0.0, "total_cost_sol": 0.0,
            "by_provider": {}, "by_agent": [],
        }
    summary = get_session_summary(task_id)

    # Convert USD cost → SOL (use live rate or fallback)
    try:
        from services.meteora_service import get_sol_usdc_rate
        rate_data = get_sol_usdc_rate()
        rate = rate_data["rate"] if rate_data else _FALLBACK_SOL_USDC_RATE
    except Exception:
        rate = _FALLBACK_SOL_USDC_RATE

    cost_sol = summary["total_cost_usd"] / rate if rate else 0.0
    summary["total_cost_sol"] = round(cost_sol, 9)
    for entry in summary.get("by_agent", []):
        entry["cost_sol"] = round(entry["cost_usd"] / rate, 9) if rate else 0.0

    return summary
