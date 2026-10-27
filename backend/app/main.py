"""
StemAI Backend — FastAPI application entry point.
"""

import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.config import settings
from app.services.firebase_service import init_firebase
from app.api.routes import router

# Path to built frontend
_FRONTEND_DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "frontend", "dist"
)
_FRONTEND_DIST = os.path.normpath(_FRONTEND_DIST)


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
        firebase_app = init_firebase()
        logger.info(f"  Firebase     : {'✓ connected' if firebase_app else '✗ not configured'}")
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

# CORS — allow all local and remote origins
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
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
        # Exceptions can contain storage paths, provider responses, or other
        # operational detail. Keep that in server logs and return a stable,
        # safe message to clients.
        content={"success": False, "error": "Internal server error"},
    )


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(router)


# ── Serve built React frontend or API info ──────────────────────────────────
if os.path.isdir(_FRONTEND_DIST):
    # Serve static assets (JS, CSS, images) from /assets
    app.mount("/assets", StaticFiles(directory=os.path.join(_FRONTEND_DIST, "assets")), name="assets")

    # Serve favicon
    @app.get("/favicon.svg")
    async def favicon():
        fav = os.path.join(_FRONTEND_DIST, "favicon.svg")
        if os.path.isfile(fav):
            return FileResponse(fav)
        return JSONResponse({"error": "not found"}, status_code=404)

    # Instant stem player (no login required)
    @app.get("/listen")
    async def listen_page():
        from fastapi.responses import HTMLResponse
        html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>StemAI — Separated Stems Player</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  body { background: #0B0F19; color: #F1F5F9; padding: 24px 16px; min-height: 100vh; display: flex; flex-direction: column; align-items: center; }
  .container { max-width: 680px; width: 100%; }
  .header { margin-bottom: 24px; text-align: center; }
  .header h1 { font-size: 26px; font-weight: 800; background: linear-gradient(135deg, #6366F1, #EC4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .header p { color: #94A3B8; font-size: 14px; margin-top: 6px; }
  .badge { display: inline-block; padding: 4px 12px; background: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 999px; font-size: 12px; font-weight: 600; margin-top: 8px; }
  .card { background: #131B2E; border: 1px solid #1E293B; border-radius: 16px; padding: 18px; margin-bottom: 14px; display: flex; flex-direction: column; gap: 10px; }
  .card-top { display: flex; justify-content: space-between; align-items: center; }
  .stem-name { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 16px; }
  .stem-icon { width: 34px; height: 34px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; }
  .dl-btn { background: #1E293B; color: #F1F5F9; border: 1px solid #334155; padding: 6px 14px; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: 600; transition: all 0.2s; }
  .dl-btn:hover { background: #6366F1; border-color: #6366F1; }
  audio { width: 100%; height: 40px; border-radius: 8px; outline: none; }
  .vocal .stem-icon { background: rgba(236, 72, 153, 0.2); }
  .drums .stem-icon { background: rgba(245, 158, 11, 0.2); }
  .bass .stem-icon { background: rgba(6, 182, 212, 0.2); }
  .other .stem-icon { background: rgba(16, 185, 129, 0.2); }
  .inst .stem-icon { background: rgba(99, 102, 241, 0.2); }
  .footer { text-align: center; color: #64748B; font-size: 12px; margin-top: 20px; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🎵 StemAI — Isolated Stems</h1>
    <p>Sabrina Carpenter — Espresso (Separated via HTDemucs AI)</p>
    <div class="badge">✓ 5 Stems Ready · 100% Completed</div>
  </div>

  <div class="card vocal">
    <div class="card-top">
      <div class="stem-name"><div class="stem-icon">🎤</div><span>Vocals (Acappella)</span></div>
      <a class="dl-btn" href="/api/files/users/guest-user/stems/job_1792946733587_fq0kwn4/vocals.mp3" download="Espresso_Vocals.mp3">⬇ Download MP3</a>
    </div>
    <audio controls src="/api/files/users/guest-user/stems/job_1792946733587_fq0kwn4/vocals.mp3"></audio>
  </div>

  <div class="card inst">
    <div class="card-top">
      <div class="stem-name"><div class="stem-icon">🎼</div><span>Instrumental (Karaoke)</span></div>
      <a class="dl-btn" href="/api/files/users/guest-user/stems/job_1792946733587_fq0kwn4/instrumental.mp3" download="Espresso_Instrumental.mp3">⬇ Download MP3</a>
    </div>
    <audio controls src="/api/files/users/guest-user/stems/job_1792946733587_fq0kwn4/instrumental.mp3"></audio>
  </div>

  <div class="card drums">
    <div class="card-top">
      <div class="stem-name"><div class="stem-icon">🥁</div><span>Drums & Percussion</span></div>
      <a class="dl-btn" href="/api/files/users/guest-user/stems/job_1792946733587_fq0kwn4/drums.mp3" download="Espresso_Drums.mp3">⬇ Download MP3</a>
    </div>
    <audio controls src="/api/files/users/guest-user/stems/job_1792946733587_fq0kwn4/drums.mp3"></audio>
  </div>

  <div class="card bass">
    <div class="card-top">
      <div class="stem-name"><div class="stem-icon">🎸</div><span>Bass</span></div>
      <a class="dl-btn" href="/api/files/users/guest-user/stems/job_1792946733587_fq0kwn4/bass.mp3" download="Espresso_Bass.mp3">⬇ Download MP3</a>
    </div>
    <audio controls src="/api/files/users/guest-user/stems/job_1792946733587_fq0kwn4/bass.mp3"></audio>
  </div>

  <div class="card other">
    <div class="card-top">
      <div class="stem-name"><div class="stem-icon">🎹</div><span>Other (Synths & Keys)</span></div>
      <a class="dl-btn" href="/api/files/users/guest-user/stems/job_1792946733587_fq0kwn4/other.mp3" download="Espresso_Other.mp3">⬇ Download MP3</a>
    </div>
    <audio controls src="/api/files/users/guest-user/stems/job_1792946733587_fq0kwn4/other.mp3"></audio>
  </div>

  <div class="footer">Stored locally at /sdcard/AGY/separated_stems/ · High Quality 320kbps MP3</div>
</div>
</body>
</html>"""
        return HTMLResponse(content=html)

    # Root: serve index.html for React Frontend
    @app.get("/")
    async def root_index():
        index = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        return JSONResponse({"error": "Frontend not built"}, status_code=404)

    # Catch-all: serve index.html for React Router (SPA)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't catch API routes or docs or listen page
        if full_path.startswith("api") or full_path.startswith("docs") or full_path.startswith("openapi") or full_path.startswith("listen"):
            return JSONResponse({"error": "not found"}, status_code=404)
        index = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        return JSONResponse({"error": "Frontend not built"}, status_code=404)

    logger.info(f"Serving frontend from: {_FRONTEND_DIST}")
else:
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
