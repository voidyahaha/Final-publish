"""
Background Job Manager.
Runs Demucs separation and vocal mixing jobs in background threads.
Updates Firestore status at every stage.
Never marks a job complete unless output files actually exist and are non-empty.
"""

import asyncio
import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Optional
from loguru import logger

from app.config import settings
from app.services.firebase_service import (
    update_job_status,
    upload_to_storage,
    download_from_storage,
    get_job,
)
from app.services.demucs_service import separate_audio, get_stem_info
from app.services.audio_analysis import analyze_audio, get_bpm_and_beats
from app.services.synchronization import time_stretch_vocal, align_vocals_to_first_beat
from app.services.mixing import (
    mix_vocal_with_instrumental,
    encode_to_mp3,
    encode_stem_to_mp3,
)

# Thread pool for background processing
_executor = ThreadPoolExecutor(max_workers=settings.MAX_CONCURRENT_JOBS)
_active_jobs: Dict[str, threading.Event] = {}
_active_jobs_lock = threading.Lock()


def get_active_job_count() -> int:
    with _active_jobs_lock:
        return len(_active_jobs)


def cancel_job(job_id: str) -> bool:
    with _active_jobs_lock:
        if job_id in _active_jobs:
            _active_jobs[job_id].set()
            return True
    return False


# ── Separation Job ───────────────────────────────────────────────────────────

def run_separation_job(
    job_id: str,
    user_id: str,
    storage_path: str,
    model: str = "htdemucs_ft",
):
    """Entry point — called in background thread."""
    cancel_event = threading.Event()
    with _active_jobs_lock:
        _active_jobs[job_id] = cancel_event

    work_dir = os.path.join(settings.PROCESSING_TEMP_DIR, job_id)
    os.makedirs(work_dir, exist_ok=True)

    try:
        _run_separation(job_id, user_id, storage_path, model, work_dir, cancel_event)
    except Exception as e:
        logger.exception(f"[{job_id}] Separation job crashed: {e}")
        asyncio.run(update_job_status(
            job_id, "failed", 0,
            f"Processing failed: {str(e)[:200]}",
            {"error": str(e)[:500]}
        ))
    finally:
        with _active_jobs_lock:
            _active_jobs.pop(job_id, None)
        # Cleanup temp dir
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
            logger.info(f"[{job_id}] Cleaned up {work_dir}")
        except Exception:
            pass


def _run_separation(job_id, user_id, storage_path, model, work_dir, cancel_event):
    """Core separation logic with Firestore status updates."""

    def check_cancel():
        if cancel_event.is_set():
            raise InterruptedError(f"Job {job_id} was cancelled")

    def progress(pct, msg):
        check_cancel()
        asyncio.run(update_job_status(job_id, "separating", pct, msg))

    logger.info(f"[{job_id}] Starting separation job | model={model}")

    # 1. Update status: processing
    asyncio.run(update_job_status(job_id, "processing", 5, "Downloading source audio..."))
    check_cancel()

    # 2. Download source file from Firebase Storage
    input_ext = os.path.splitext(storage_path)[1] or ".mp3"
    input_path = os.path.join(work_dir, f"input{input_ext}")
    asyncio.run(download_from_storage(storage_path, input_path))

    if not os.path.exists(input_path) or os.path.getsize(input_path) < 100:
        raise RuntimeError(f"Downloaded file is missing or empty: {input_path}")

    logger.info(f"[{job_id}] Downloaded: {input_path} ({os.path.getsize(input_path)//1024}KB)")

    # 3. Audio analysis (BPM, key, duration)
    asyncio.run(update_job_status(job_id, "processing", 12, "Analyzing audio (BPM, key)..."))
    check_cancel()

    analysis = {}
    try:
        analysis = analyze_audio(input_path)
        logger.info(f"[{job_id}] Analysis: BPM={analysis.get('bpm')}, key={analysis.get('key')}")
    except Exception as e:
        logger.warning(f"[{job_id}] Analysis failed (non-fatal): {e}")

    # 4. Run Demucs separation
    stems_dir = os.path.join(work_dir, "stems")
    os.makedirs(stems_dir, exist_ok=True)

    check_cancel()
    asyncio.run(update_job_status(job_id, "separating", 20, f"Loading AI model ({model})..."))

    stem_files = separate_audio(
        input_path=input_path,
        output_dir=stems_dir,
        model_name=model,
        on_progress=progress,
    )

    if not stem_files:
        raise RuntimeError("Demucs returned no stems")

    check_cancel()

    # 5. Upload stems to Firebase Storage
    asyncio.run(update_job_status(job_id, "separating", 88, "Uploading stems to storage..."))

    stems_data = []
    for stem_name, local_path in stem_files.items():
        check_cancel()

        if not os.path.exists(local_path) or os.path.getsize(local_path) < 1000:
            logger.warning(f"[{job_id}] Stem {stem_name} missing or too small, skipping")
            continue

        stem_info = get_stem_info(local_path)

        # Upload as MP3 for final delivery (WAV processing done, encode now)
        mp3_path = local_path.replace(".wav", ".mp3")
        try:
            encode_stem_to_mp3(local_path, mp3_path, bitrate=settings.FINAL_BITRATE)
            upload_local_path = mp3_path
            content_type = "audio/mpeg"
            upload_ext = ".mp3"
        except Exception as e:
            logger.warning(f"[{job_id}] MP3 encode failed for {stem_name}, uploading WAV: {e}")
            upload_local_path = local_path
            content_type = "audio/wav"
            upload_ext = ".wav"

        storage_stem_path = f"users/{user_id}/stems/{job_id}/{stem_name}{upload_ext}"
        download_url = asyncio.run(upload_to_storage(
            upload_local_path, storage_stem_path, content_type
        ))

        stems_data.append({
            "stem": stem_name,
            "storagePath": storage_stem_path,
            "downloadUrl": download_url,
            "duration": stem_info.get("duration"),
            "sampleRate": stem_info.get("sample_rate"),
            "sizBytes": stem_info.get("size_bytes"),
        })

    if not stems_data:
        raise RuntimeError("No stems were successfully uploaded")

    # 6. Mark completed
    asyncio.run(update_job_status(
        job_id, "completed", 100,
        f"Separation complete! {len(stems_data)} stems ready",
        {
            "stems": stems_data,
            "bpm": analysis.get("bpm"),
            "key": analysis.get("key"),
            "duration": analysis.get("duration"),
        }
    ))

    logger.info(f"[{job_id}] Separation COMPLETE — {len(stems_data)} stems")


# ── Vocal Mix Job ────────────────────────────────────────────────────────────

def run_vocal_mix_job(
    job_id: str,
    user_id: str,
    vocal_path: str,
    instrumental_path: str,
    vocal_gain: float = 0.85,
    instrumental_gain: float = 1.0,
    time_stretch: bool = True,
):
    """Entry point for vocal mix job — called in background thread."""
    cancel_event = threading.Event()
    with _active_jobs_lock:
        _active_jobs[job_id] = cancel_event

    work_dir = os.path.join(settings.PROCESSING_TEMP_DIR, job_id)
    os.makedirs(work_dir, exist_ok=True)

    try:
        _run_vocal_mix(
            job_id, user_id, vocal_path, instrumental_path,
            vocal_gain, instrumental_gain, time_stretch, work_dir, cancel_event
        )
    except Exception as e:
        logger.exception(f"[{job_id}] Vocal mix job crashed: {e}")
        asyncio.run(update_job_status(
            job_id, "failed", 0,
            f"Mixing failed: {str(e)[:200]}",
            {"error": str(e)[:500]}
        ))
    finally:
        with _active_jobs_lock:
            _active_jobs.pop(job_id, None)
        shutil.rmtree(work_dir, ignore_errors=True)
        logger.info(f"[{job_id}] Cleaned up {work_dir}")


def _run_vocal_mix(
    job_id, user_id, vocal_storage_path, instrumental_storage_path,
    vocal_gain, instrumental_gain, do_time_stretch, work_dir, cancel_event
):
    def check_cancel():
        if cancel_event.is_set():
            raise InterruptedError(f"Job {job_id} cancelled")

    def status(pct, msg, state="mixing"):
        check_cancel()
        asyncio.run(update_job_status(job_id, state, pct, msg))

    logger.info(f"[{job_id}] Starting vocal mix")

    # 1. Download both files
    status(5, "Downloading audio files...", "processing")

    vocal_ext = os.path.splitext(vocal_storage_path)[1] or ".webm"
    inst_ext = os.path.splitext(instrumental_storage_path)[1] or ".mp3"

    vocal_local = os.path.join(work_dir, f"vocal{vocal_ext}")
    inst_local = os.path.join(work_dir, f"instrumental{inst_ext}")

    asyncio.run(download_from_storage(vocal_storage_path, vocal_local))
    asyncio.run(download_from_storage(instrumental_storage_path, inst_local))

    for f in [vocal_local, inst_local]:
        if not os.path.exists(f) or os.path.getsize(f) < 100:
            raise RuntimeError(f"Downloaded file missing: {f}")

    # 2. Convert vocal to WAV if needed (webm/m4a etc)
    vocal_wav = os.path.join(work_dir, "vocal.wav")
    _convert_to_wav(vocal_local, vocal_wav)

    inst_wav = os.path.join(work_dir, "instrumental.wav")
    _convert_to_wav(inst_local, inst_wav)

    check_cancel()
    status(15, "Analyzing BPM...", "processing")

    # 3. Analyze BPM of both
    try:
        inst_bpm, _, _ = get_bpm_and_beats(inst_wav)
        vocal_bpm, _, _ = get_bpm_and_beats(vocal_wav)
        logger.info(f"[{job_id}] Vocal BPM={vocal_bpm:.1f}, Inst BPM={inst_bpm:.1f}")
    except Exception as e:
        logger.warning(f"[{job_id}] BPM detection failed: {e}")
        inst_bpm, vocal_bpm = 120.0, 120.0

    check_cancel()

    # 4. Time-stretch vocal if needed
    if do_time_stretch and abs(vocal_bpm - inst_bpm) > 2.0:
        status(30, f"Time-stretching vocal ({vocal_bpm:.0f} → {inst_bpm:.0f} BPM)...", "mixing")
        stretched_vocal = os.path.join(work_dir, "vocal_stretched.wav")
        time_stretch_vocal(vocal_wav, inst_bpm, vocal_bpm, stretched_vocal)
        vocal_wav = stretched_vocal
    else:
        status(30, "BPM matched, aligning to first beat...", "mixing")

    # 5. Align vocal to first beat
    check_cancel()
    status(45, "Aligning vocal to instrumental beat grid...", "mixing")
    vocal_aligned = os.path.join(work_dir, "vocal_aligned.wav")
    align_vocals_to_first_beat(vocal_wav, inst_wav, vocal_aligned)
    vocal_wav = vocal_aligned

    # 6. Mix
    check_cancel()
    status(60, "Mixing vocal with instrumental...", "mixing")
    mixed_wav = os.path.join(work_dir, "mixed.wav")
    mix_vocal_with_instrumental(
        vocal_wav, inst_wav, mixed_wav, vocal_gain, instrumental_gain
    )

    # 7. Encode to MP3
    check_cancel()
    status(80, "Encoding final mix to MP3...", "mixing")
    mixed_mp3 = os.path.join(work_dir, "mixed.mp3")
    encode_to_mp3(mixed_wav, mixed_mp3, bitrate=settings.FINAL_BITRATE)

    if not os.path.exists(mixed_mp3) or os.path.getsize(mixed_mp3) < 1000:
        raise RuntimeError("Final mix file is missing or empty after encoding")

    # 8. Upload
    status(90, "Uploading final mix...", "mixing")
    storage_mix_path = f"users/{user_id}/mixes/{job_id}/mixed.mp3"
    download_url = asyncio.run(upload_to_storage(mixed_mp3, storage_mix_path, "audio/mpeg"))

    # 9. Done
    asyncio.run(update_job_status(
        job_id, "completed", 100,
        "Mix complete! Your track is ready.",
        {
            "mixedTrackPath": storage_mix_path,
            "mixedTrackUrl": download_url,
            "vocalBpm": vocal_bpm,
            "instrumentalBpm": inst_bpm,
        }
    ))
    logger.info(f"[{job_id}] Vocal mix COMPLETE")


def _convert_to_wav(input_path: str, output_path: str):
    """Convert any audio to 44100Hz WAV using ffmpeg."""
    import subprocess
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-acodec", "pcm_s24le",
        "-ar", "44100",
        "-ac", "2",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg conversion failed: {result.stderr[-500:]}")
    logger.info(f"Converted {input_path} -> {output_path}")


# ── Dispatch helpers (called from API routes) ────────────────────────────────

def dispatch_separation(job_id, user_id, storage_path, model="htdemucs_ft"):
    """Submit separation job to thread pool."""
    logger.info(f"Dispatching separation job: {job_id}")
    _executor.submit(run_separation_job, job_id, user_id, storage_path, model)


def dispatch_vocal_mix(job_id, user_id, vocal_path, instrumental_path,
                       vocal_gain=0.85, instrumental_gain=1.0, time_stretch=True):
    """Submit vocal mix job to thread pool."""
    logger.info(f"Dispatching vocal mix job: {job_id}")
    _executor.submit(
        run_vocal_mix_job, job_id, user_id, vocal_path,
        instrumental_path, vocal_gain, instrumental_gain, time_stretch
    )
