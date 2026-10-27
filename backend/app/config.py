import os
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path

class Settings(BaseSettings):
    # App
    APP_NAME: str = "StemAI Backend"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Firebase Admin
    FIREBASE_PROJECT_ID: str = "vocal-separater-5eb7c"
    FIREBASE_CREDENTIALS_PATH: str = ""  # Path to service account JSON
    FIREBASE_SERVICE_ACCOUNT_JSON: str = ""  # Optional JSON secret for container platforms
    FIREBASE_STORAGE_BUCKET: str = "vocal-separater-5eb7c.firebasestorage.app"

    # Processing
    DEMUCS_MODEL: str = "htdemucs"     # Best balance of speed & quality
    DEMUCS_SHIFTS: int = 0             # 0 for fast single-pass inference on CPU
    DEMUCS_OVERLAP: float = 0.25       # Chunk overlap
    PROCESSING_TEMP_DIR: str = "/data/data/com.termux/files/usr/tmp/stemai_processing"
    AUDIO_DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    MAX_CONCURRENT_JOBS: int = 2
    MAX_UPLOAD_MB: int = 250
    CORS_ORIGINS: str = "http://localhost:5173"

    # Audio
    OUTPUT_FORMAT: str = "wav"         # Internal processing format
    FINAL_FORMAT: str = "mp3"          # Final output format
    FINAL_BITRATE: str = "320k"
    SAMPLE_RATE: int = 44100
    TARGET_LUFS: float = -14.0        # Streaming loudness target

    # Timeouts
    SEPARATION_TIMEOUT: int = 3600     # 1 hour max per job
    UPLOAD_TIMEOUT: int = 600          # 10 min upload

    # Redis (for job queue, optional)
    REDIS_URL: str = "redis://localhost:6379/0"
    USE_CELERY: bool = False           # False = use asyncio background tasks

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",  # Allow extra env vars like DEMUCS_DEVICE
    }

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

# Ensure dirs exist
Path(settings.PROCESSING_TEMP_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.AUDIO_DATA_DIR).mkdir(parents=True, exist_ok=True)
