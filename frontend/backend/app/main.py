"""
StemAI Backend — FastAPI application entry point.
"""

import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import settings
from app.services.firebase_service import init_firebase
from app.api.routes import router


# ── Logging setup ─────────────────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan> - {message}",
    level="DEBUG" if settings.DEBUG else "INFO",
    colorize=True,
)
logger.add(
    "logs/stemai.log",
    rotation="50 MB",
    retention="7 days",
    level="DEBUG",
    enqueue=True,
)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown."""
    logger.info("=" * 60)
    logger.info("StemAI Backend starting...")
    logger.info(f"  Demucs model : {settings.DEMUCS_MODEL}")
    logger.info(f"  Max jobs     : {settings.MAX_CONCURRENT_JOBS}")
    logger.info(f"  Temp dir     : {settings.PROCESSING_TEMP_DIR}")

    # Initialize Firebase
    try:
        init_firebase()
        logger.info("  Firebase     : ✓ connected")
    except Exception as e:
        logger.error(f"  Firebase     : ✗ {e}")
        logger.warning("  Running without Firebase — some features will fail")

    # Log GPU status
    from app.services.demucs_service import GPU_AVAILABLE, DEVICE
    logger.info(f"  Device       : {DEVICE} {'(GPU ✓)' if GPU_AVAILABLE else '(CPU)'}")
    logger.info("=" * 60)

    yield

    logger.info("StemAI Backend shutting down...")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="StemAI API",
    description="AI-powered music stem separation and vocal mixing",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend origins
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://*.vercel.app",
    "https://vocal-separater-5eb7c.web.app",
    "https://vocal-separater-5eb7c.firebaseapp.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],         # Tighten in production to ALLOWED_ORIGINS
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": str(exc)},
    )


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(router)


@app.get("/")
async def root():
    return {
        "name": "StemAI API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


# ── Dev runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    import os
    os.makedirs("logs", exist_ok=True)
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1,         # 1 worker — Demucs is memory-heavy
        timeout_keep_alive=120,
    )
