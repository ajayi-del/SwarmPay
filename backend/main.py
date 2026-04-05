"""
SwarmPay Backend — FastAPI application entry point.

Production hardening:
  • CORS restricted to configured origins (ALLOWED_ORIGINS env var)
  • Rate limiting via slowapi (10 req/min task endpoints, 30 req/min others)
  • Startup env validation — crashes fast if required vars missing
  • Global error handler hides internals in production
  • Admin key required to toggle live/dry-run mode
  • Structured request logging
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import uvicorn

from routers import tasks, audit, regis
from routers import sovereignty

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("swarmpay")

# ── Rate limiter ───────────────────────────────────────────────────────────────
# Railway (and most PaaS) reverse proxies forward the real client IP in
# X-Forwarded-For. slowapi's get_remote_address reads request.client.host which
# is the proxy's IP — all clients would share one bucket. Use
# X-Forwarded-For header instead so each real client IP gets its own limit.

def _real_client_ip(request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        # X-Forwarded-For can be a comma-separated list; first is the client
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(key_func=_real_client_ip, default_limits=["60/minute"])


# ── Startup validation ─────────────────────────────────────────────────────────

def _validate_env() -> None:
    """Crash fast if any required env var is missing."""
    required = {
        "ANTHROPIC_API_KEY": "Claude API — get from console.anthropic.com",
    }
    missing = [f"{k} ({hint})" for k, hint in required.items() if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            f"FATAL: missing required environment variables:\n  " + "\n  ".join(missing)
        )
    # Warn about optional but important vars
    optional_warn = ["DEEPSEEK_API_KEY", "POCKETBASE_URL", "TELEGRAM_BOT_TOKEN"]
    for var in optional_warn:
        if not os.environ.get(var):
            logger.warning("Optional env var not set: %s — related features will degrade", var)


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_env()
    logger.info("SwarmPay starting — environment validated")

    # Telegram bot — fire and forget, non-blocking
    tg_task = None
    try:
        from services.telegram_service import poll_loop
        tg_task = asyncio.create_task(poll_loop())
        logger.info("Telegram bot polling started")
    except Exception as exc:
        logger.warning("Telegram bot failed to start: %s", exc)

    yield

    if tg_task and not tg_task.done():
        tg_task.cancel()
        logger.info("Telegram bot stopped")


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SwarmPay API",
    description="AI agent swarm with OWS wallet integration, Solana payments, and REGIS governance",
    version="2.0.0",
    lifespan=lifespan,
    # Hide schema in production
    docs_url="/docs" if os.environ.get("ENVIRONMENT") != "production" else None,
    redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ───────────────────────────────────────────────────────────────────────
# Default: allow Railway + Vercel deployment URLs.
# Override with ALLOWED_ORIGINS=https://yourdomain.com,https://other.com

_raw_origins = os.environ.get("ALLOWED_ORIGINS", "")
if _raw_origins.strip():
    ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
else:
    # Permissive defaults for local dev and first Railway deploy
    # Tighten with ALLOWED_ORIGINS once you have a stable domain
    ALLOWED_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Key"],
)

# ── Request logging middleware ─────────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.monotonic()
    response = await call_next(request)
    ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "%s %s → %d (%dms)",
        request.method, request.url.path, response.status_code, ms,
    )
    return response

# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(tasks.router)
app.include_router(audit.router)
app.include_router(regis.router)
app.include_router(sovereignty.router)


# ── Health / root ──────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service": "SwarmPay API",
        "version": "2.0.0",
        "status": "running",
        "project": "grand-fulfillment",
        "environment": os.environ.get("ENVIRONMENT", "development"),
    }


@app.get("/health")
async def health_check():
    """Comprehensive health check — tests each service connection."""
    from datetime import datetime, timezone

    checks: dict[str, str] = {}

    # PocketBase
    try:
        from services.pocketbase import PocketBaseService
        PocketBaseService().list("tasks", limit=1)
        checks["pocketbase"] = "ok"
    except Exception:
        checks["pocketbase"] = "error"

    # Anthropic key present + reachable
    try:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        checks["anthropic"] = "ok" if key and key.startswith("sk-ant-") else "no_key"
    except Exception:
        checks["anthropic"] = "error"

    # DeepSeek key
    try:
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        checks["deepseek"] = "ok" if key else "no_key"
    except Exception:
        checks["deepseek"] = "error"

    # Solana devnet RPC ping
    try:
        import httpx as _hx
        rpc = os.environ.get("SOLANA_RPC_URL", "https://api.devnet.solana.com")
        r = _hx.post(rpc, json={"jsonrpc": "2.0", "id": 1, "method": "getHealth"}, timeout=4)
        checks["solana"] = "ok" if r.status_code == 200 else "error"
    except Exception:
        checks["solana"] = "unreachable"

    # Telegram bot token present
    try:
        tok = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        checks["telegram"] = "ok" if tok else "no_token"
    except Exception:
        checks["telegram"] = "error"

    # MoonPay key present
    try:
        mpk = os.environ.get("MOONPAY_PUBLIC_KEY", "")
        checks["moonpay"] = "ok" if mpk else "no_key"
    except Exception:
        checks["moonpay"] = "error"

    all_critical = all(
        checks.get(s) == "ok"
        for s in ("pocketbase", "anthropic", "solana")
    )

    return {
        "status": "healthy" if all_critical else "degraded",
        **checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }


# ── Analytics ─────────────────────────────────────────────────────────────────

@app.get("/analytics/tokens/today")
async def analytics_tokens_today():
    """Approximate token usage from today's sub-task outputs."""
    import json as _json
    from datetime import datetime, timezone, timedelta
    try:
        from services.pocketbase import PocketBaseService
        pb = PocketBaseService()
        today = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        tasks_today = pb.list("tasks", limit=100, sort="-created")
        sub_tasks = pb.list("sub_tasks", limit=200, sort="-created")
        payments = pb.list("payments", limit=200, sort="-created")

        total_tokens = 0
        for st in sub_tasks:
            out = st.get("output", "")
            if not out:
                continue
            try:
                text = _json.loads(out).get("text", out)
            except Exception:
                text = out
            total_tokens += max(0, len(text) // 4)

        total_signed = sum(1 for p in payments if p.get("status") == "signed")
        total_usdc = sum(
            float(p.get("amount", 0)) for p in payments if p.get("status") == "signed"
        )
        x402_count = sum(
            1 for p in payments
            if "x402" in (p.get("policy_reason") or "").lower()
        )

        return {
            "period": "last_24h",
            "tasks_run": len(tasks_today),
            "tokens_estimated": total_tokens,
            "payments_signed": total_signed,
            "usdc_processed": round(total_usdc, 4),
            "x402_transactions": x402_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"period": "last_24h", "error": str(e), "tokens_estimated": 0}


# ── Dry Run / Live Mode ────────────────────────────────────────────────────────

def _live_mode() -> bool:
    return os.environ.get("LIVE_MODE", "false").lower() in ("true", "1", "yes")


@app.get("/mode")
async def get_mode():
    live = _live_mode()
    return {
        "mode": "live" if live else "dry_run",
        "live": live,
        "description": (
            "Real Solana devnet transactions" if live
            else "Mock wallets and signatures — safe to demo"
        ),
    }


@app.post("/mode/toggle")
async def toggle_mode(x_admin_key: str = Header(default=None, alias="X-Admin-Key")):
    """
    Toggle live/dry-run mode. Requires X-Admin-Key header.
    Set ADMIN_API_KEY env var. Defaults to a random key if not set (effectively disabled).
    """
    admin_key = os.environ.get("ADMIN_API_KEY", "")
    if not admin_key or x_admin_key != admin_key:
        raise HTTPException(status_code=403, detail="Invalid or missing admin key")

    current = _live_mode()
    new_val = "false" if current else "true"
    os.environ["LIVE_MODE"] = new_val
    live = new_val == "true"
    logger.warning("Mode toggled to %s by admin", "LIVE" if live else "DRY_RUN")
    return {
        "mode": "live" if live else "dry_run",
        "live": live,
        "message": f"Switched to {'LIVE' if live else 'DRY RUN'} mode",
    }


# ── Global error handler ───────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    # Never leak internal details to client
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check server logs."},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    logger.warning("Validation error on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=400, content={"detail": str(exc)})


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=os.environ.get("ENVIRONMENT") != "production",
        log_level="info",
    )
