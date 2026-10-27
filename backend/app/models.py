from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime

class JobStatus(str, Enum):
    queued = "queued"
    uploading = "uploading"
    processing = "processing"
    separating = "separating"
    mixing = "mixing"
    completed = "completed"
    failed = "failed"

class StemType(str, Enum):
    vocals = "vocals"
    drums = "drums"
    bass = "bass"
    other = "other"
    instrumental = "instrumental"
    piano = "piano"
    guitar = "guitar"

class StemFile(BaseModel):
    stem: StemType
    storage_path: str
    download_url: str
    duration: Optional[float] = None
    sample_rate: Optional[int] = None
    size_bytes: Optional[int] = None

class Job(BaseModel):
    id: str
    user_id: str
    type: str  # separation | vocal_mix
    status: JobStatus = JobStatus.queued
    progress: int = 0
    status_message: str = "Queued"
    original_file_name: str
    original_storage_path: str
    original_download_url: Optional[str] = None
    stems: List[StemFile] = []
    mixed_track_path: Optional[str] = None
    mixed_track_url: Optional[str] = None
    bpm: Optional[float] = None
    key: Optional[str] = None
    duration: Optional[float] = None
    error: Optional[str] = None
    model: str = "htdemucs_ft"
    vocal_storage_path: Optional[str] = None
    instrumental_storage_path: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

# ── Request/Response Models ─────────────────────────────────────────────────

class SeparationRequest(BaseModel):
    job_id: str
    user_id: str
    storage_path: str
    model: str = "htdemucs_ft"

class MixRequest(BaseModel):
    job_id: str
    user_id: str
    vocal_path: str
    instrumental_path: str
    vocal_gain: float = Field(default=0.85, ge=0.0, le=2.0)
    instrumental_gain: float = Field(default=1.0, ge=0.0, le=2.0)
    time_stretch: bool = True

class AnalyzeRequest(BaseModel):
    storage_path: str

class AudioAnalysis(BaseModel):
    bpm: float
    key: Optional[str] = None
    duration: float
    sample_rate: int
    loudness: float
    beats: List[float] = []
    onsets: List[float] = []

class HealthResponse(BaseModel):
    status: str
    gpu_available: bool
    demucs_model: str
    active_jobs: int
    version: str = "1.0.0"
