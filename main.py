"""
main.py — AI Content Synthesis Engine entry point.
Run: uvicorn main:app --reload --port 8000
"""
import os
import sys
import asyncio
import sys

# Windows Proactor Event Loop Policy is required for Playwright/Subprocesses
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Fix Windows cp1252 unicode encoding crash
os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.logging import configure_logging, get_logger
from app.api.v1.router import api_router
from utils.file_utils import ensure_dirs

# ── Windows Proactor Fix ────────────────────────────────────────────────────
# This MUST be set at the top level before any loops are created
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

settings = get_settings()
configure_logging()
logger = get_logger("startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Windows Proactor Fix ────────────────────────────────────────────────
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    configure_logging()
    logger = get_logger("startup")
    
    # ── Pre-flight Checks ───────────────────────────────────────────────────
    error_found = False
    
    # Check .env
    from pathlib import Path
    if not Path(".env").exists():
        logger.error("startup_failed_missing_env", details="No .env file found. Copy .env.example and fill it.")
        error_found = True
        
    # Check credentials.json
    if not Path(settings.gdrive_credentials_json).exists():
        logger.warning("startup_config_missing", file=settings.gdrive_credentials_json, details="Google Drive upload will fail until this file is added.")

    ensure_dirs(settings.output_dir, settings.temp_dir)
    
    if error_found:
        logger.critical("engine_halted", reason="Missing critical configuration. See logs above.")
        # We don't exit(1) here to allow the process to stay alive for debugging/API health checks,
        # but we've logged clearly what's wrong.
    else:
        logger.info(
            "engine_started",
            env=settings.app_env,
            output_dir=settings.output_dir,
        )

    yield  # ── App running ──

    logger.info("engine_shutdown")


app = FastAPI(
    title="AI Content Synthesis Engine",
    description=(
        "Discovers trending topics, generates Reel scripts + LinkedIn posts via Gemini, "
        "renders MP4 with MoviePy, and delivers assets to Google Drive."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


# ── Dev runner ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
