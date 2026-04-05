"""
SwarmPay Backend - FastAPI main application
"""

import asyncio
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from routers import tasks, audit, regis


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background services on startup."""
    # Telegram bot — fire and forget, non-blocking
    try:
        from services.telegram_service import poll_loop
        tg_task = asyncio.create_task(poll_loop())
    except Exception as e:
        print(f"[telegram] Startup error: {e}")
        tg_task = None
    yield
    # Shutdown
    if tg_task and not tg_task.done():
        tg_task.cancel()


app = FastAPI(
    title="SwarmPay API",
    description="Agent swarm dispatcher with OWS wallet integration",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for Railway/Vercel deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router)
app.include_router(audit.router)
app.include_router(regis.router)


@app.get("/")
async def root():
    return {"message": "SwarmPay API", "version": "2.0.0", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ── Dry Run / Live Mode toggle ─────────────────────────────────────────────────

def _live_mode() -> bool:
    return os.environ.get("LIVE_MODE", "false").lower() in ("true", "1", "yes")


@app.get("/mode")
async def get_mode():
    """Return current execution mode."""
    live = _live_mode()
    return {
        "mode": "live" if live else "dry_run",
        "live": live,
        "description": "Real Solana devnet transactions" if live else "Mock wallets and signatures — safe to demo",
    }


@app.post("/mode/toggle")
async def toggle_mode():
    """Toggle between dry run and live mode (runtime only — persists until restart)."""
    current = _live_mode()
    new_val = "false" if current else "true"
    os.environ["LIVE_MODE"] = new_val
    live = new_val == "true"
    return {
        "mode": "live" if live else "dry_run",
        "live": live,
        "message": f"Switched to {'LIVE' if live else 'DRY RUN'} mode",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
