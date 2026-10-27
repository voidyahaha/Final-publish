"""
FastAPI route definitions.
All endpoints require Firebase ID token authentication.
"""

import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Header
from fastapi.responses import JSONResponse
from loguru import logger
from typing import Optional

from app.models import (
    SeparationRequest, MixRequest, AnalyzeRequest,
    HealthResponse, Job, JobStatus,
)
from app.config import settings
from app.services.firebase_service import (
    update_job_status, get_job, get_user_jobs, upload_to_storage,
)
from app.services.job_manager import (
    dispatch_separation, dispatch_vocal_mix,
    get_active_job_count, cancel_job,
)
from app.services.audio_analysis import analyze_audio
from app.services.demucs_service import GPU_AVAILABLE, DEVICE

router = APIRouter(prefix="/api")

# ── Auth helper ──────────────────────────────────────────────────────────────

async def verify_firebase_token(authorization: Optional[str] = Header(None)) -> dict:
    """Verify Firebase ID token from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.replace("Bearer ", "")
    try:
        from firebase_admin import auth as fb_auth
        decoded = fb_auth.verify_id_token(token)
        return decoded
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


# ── Health ───────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint — no auth required."""
    return HealthResponse(
        status="ok",
        gpu_available=GPU_AVAILABLE,
        demucs_model=settings.DEMUCS_MODEL,
        active_jobs=get_active_job_count(),
    )


# ── Upload ───────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    folder: str = Form(default="originals"),
    token_data: dict = Depends(verify_firebase_token),
):
    """
    Upload audio file to Firebase Storage via backend.
    Validates file type and size before uploading.
    """
    # Validate user matches token
    if token_data.get("uid") != user_id:
        raise HTTPException(status_code=403, detail="User ID mismatch")

    # Validate content type
    allowed_types = {
        "audio/mpeg", "audio/mp3", "audio/wav", "audio/wave",
        "audio/x-wav", "audio/flac", "audio/x-flac", "audio/mp4",
        "audio/m4a", "audio/aac", "audio/ogg", "audio/webm",
        "video/mp4",
    }
    content_type = file.content_type or ""
    filename = file.filename or "audio"
    ext = os.path.splitext(filename)[1].lower()
    allowed_exts = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".webm"}

    if content_type not in allowed_types and ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type or ext}"
        )

    # Read file and check size
    MAX_SIZE = 200 * 1024 * 1024  # 200 MB
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 200MB)")
    if len(content) < 1000:
        raise HTTPException(status_code=400, detail="File too small to be valid audio")

    # Save to temp
    temp_path = os.path.join(settings.PROCESSING_TEMP_DIR, f"upload_{uuid.uuid4()}{ext}")
    try:
        with open(temp_path, "wb") as f:
            f.write(content)

        # Upload to Firebase Storage
        timestamp = int(__import__("time").time())
        storage_path = f"users/{user_id}/{folder}/{timestamp}_{filename}"
        download_url = await upload_to_storage(
            temp_path, storage_path, content_type or "audio/mpeg"
        )

        return {
            "success": True,
            "storage_path": storage_path,
            "download_url": download_url,
            "file_name": filename,
            "size": len(content),
        }
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ── Separation ───────────────────────────────────────────────────────────────

@router.post("/separate")
async def start_separation(
    request: SeparationRequest,
    token_data: dict = Depends(verify_firebase_token),
):
    """Enqueue a Demucs stem separation job."""
    if token_data.get("uid") != request.user_id:
        raise HTTPException(status_code=403, detail="User ID mismatch")

    if not request.storage_path:
        raise HTTPException(status_code=400, detail="storage_path is required")

    if get_active_job_count() >= settings.MAX_CONCURRENT_JOBS * 2:
        raise HTTPException(status_code=503, detail="Server busy, please try again shortly")

    # Mark job as queued in Firestore
    await update_job_status(
        request.job_id, "processing", 3,
        "Job accepted, downloading audio..."
    )

    # Dispatch to background thread
    dispatch_separation(
        job_id=request.job_id,
        user_id=request.user_id,
        storage_path=request.storage_path,
        model=request.model or settings.DEMUCS_MODEL,
    )

    logger.info(f"Separation dispatched: {request.job_id}")
    return {"success": True, "job_id": request.job_id, "status": "processing"}


# ── Vocal Mix ────────────────────────────────────────────────────────────────

@router.post("/mix")
async def start_vocal_mix(
    request: MixRequest,
    token_data: dict = Depends(verify_firebase_token),
):
    """Enqueue a vocal mix job."""
    if token_data.get("uid") != request.user_id:
        raise HTTPException(status_code=403, detail="User ID mismatch")

    if not request.vocal_path or not request.instrumental_path:
        raise HTTPException(status_code=400, detail="vocal_path and instrumental_path are required")

    await update_job_status(
        request.job_id, "processing", 3,
        "Mix job accepted, downloading audio..."
    )

    dispatch_vocal_mix(
        job_id=request.job_id,
        user_id=request.user_id,
        vocal_path=request.vocal_path,
        instrumental_path=request.instrumental_path,
        vocal_gain=request.vocal_gain,
        instrumental_gain=request.instrumental_gain,
        time_stretch=request.time_stretch,
    )

    logger.info(f"Vocal mix dispatched: {request.job_id}")
    return {"success": True, "job_id": request.job_id, "status": "processing"}


# ── Job Status ───────────────────────────────────────────────────────────────

@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    token_data: dict = Depends(verify_firebase_token),
):
    """Get current job status from Firestore."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Verify ownership
    if job.get("userId") != token_data.get("uid"):
        raise HTTPException(status_code=403, detail="Access denied")

    return {"success": True, "job": job}


@router.get("/jobs/user/{user_id}")
async def get_user_job_list(
    user_id: str,
    token_data: dict = Depends(verify_firebase_token),
):
    """Get all jobs for a user."""
    if token_data.get("uid") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    jobs = await get_user_jobs(user_id)
    return {"success": True, "jobs": jobs, "count": len(jobs)}


@router.delete("/jobs/{job_id}")
async def cancel_job_endpoint(
    job_id: str,
    token_data: dict = Depends(verify_firebase_token),
):
    """Cancel a running job."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("userId") != token_data.get("uid"):
        raise HTTPException(status_code=403, detail="Access denied")

    cancelled = cancel_job(job_id)
    if cancelled:
        await update_job_status(job_id, "failed", 0, "Cancelled by user",
                                {"error": "Cancelled by user"})

    return {"success": True, "cancelled": cancelled}


# ── Audio Analysis ───────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_audio_endpoint(
    request: AnalyzeRequest,
    token_data: dict = Depends(verify_firebase_token),
):
    """Analyze audio for BPM, key, beats, etc."""
    import tempfile
    from app.services.firebase_service import download_from_storage

    ext = os.path.splitext(request.storage_path)[1] or ".mp3"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await download_from_storage(request.storage_path, tmp_path)
        result = analyze_audio(tmp_path)
        return {"success": True, "analysis": result}
    except Exception as e:
        logger.exception(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
