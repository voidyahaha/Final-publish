import firebase_admin
from firebase_admin import credentials, firestore, storage as fb_storage
from app.config import settings
from loguru import logger
import os
import json
import shutil
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

_firebase_app = None
_local_jobs: Dict[str, Dict[str, Any]] = {}

LOCAL_STORAGE_DIR = os.path.join(settings.AUDIO_DATA_DIR, "storage")
os.makedirs(LOCAL_STORAGE_DIR, exist_ok=True)



def firebase_ready() -> bool:
    """Return whether the Admin SDK has been initialized for this process."""
    return _firebase_app is not None

def init_firebase():
    """Initialize Firebase Admin SDK."""
    global _firebase_app
    if _firebase_app:
        return _firebase_app

    try:
        cred_path = settings.FIREBASE_CREDENTIALS_PATH

        if settings.FIREBASE_SERVICE_ACCOUNT_JSON:
            cred = credentials.Certificate(json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON))
            logger.info("Firebase: using service account JSON from environment")
        elif cred_path and os.path.exists(cred_path):
            # Use explicit service account file
            cred = credentials.Certificate(cred_path)
            logger.info(f"Firebase: using credentials from {cred_path}")
        elif os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            # Use application default credentials
            cred = credentials.ApplicationDefault()
            logger.info("Firebase: using application default credentials")
        else:
            # Try to initialize without explicit credentials (works in GCP/Cloud Run)
            try:
                cred = credentials.ApplicationDefault()
                logger.info("Firebase: using implicit application default credentials")
            except Exception:
                # Last resort: use a minimal credential setup for emulator/testing
                logger.warning("Firebase: no credentials found, running in limited mode")
                return None

        _firebase_app = firebase_admin.initialize_app(cred, {
            'storageBucket': settings.FIREBASE_STORAGE_BUCKET,
            'projectId': settings.FIREBASE_PROJECT_ID,
        })
        logger.info("Firebase Admin SDK initialized successfully")
        return _firebase_app
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
        raise

def get_firestore():
    """Get Firestore client."""
    if not firebase_ready():
        raise RuntimeError("Firebase Admin is not configured. Set GOOGLE_APPLICATION_CREDENTIALS or FIREBASE_CREDENTIALS_PATH.")
    return firestore.client()

def get_storage_bucket():
    """Get Firebase Storage bucket."""
    if not firebase_ready():
        raise RuntimeError("Firebase Admin is not configured. Set FIREBASE_STORAGE_BUCKET and server credentials.")
    return fb_storage.bucket()

async def update_job_status(
    job_id: str,
    status: str,
    progress: int,
    status_message: str,
    extra: Optional[Dict[str, Any]] = None
):
    """Update job status in Firestore and local in-memory store."""
    update_data = {
        'id': job_id,
        'status': status,
        'progress': progress,
        'statusMessage': status_message,
        'updatedAt': datetime.now(timezone.utc),
    }
    if extra:
        update_data.update(extra)

    if status == 'completed':
        update_data['completedAt'] = datetime.now(timezone.utc)

    # Update in-memory job store
    if job_id not in _local_jobs:
        _local_jobs[job_id] = {}
    _local_jobs[job_id].update(update_data)

    try:
        if firebase_ready():
            db = get_firestore()
            fs_data = dict(update_data)
            fs_data['updatedAt'] = firestore.SERVER_TIMESTAMP
            if status == 'completed':
                fs_data['completedAt'] = firestore.SERVER_TIMESTAMP
            db.collection('jobs').document(job_id).set(fs_data, merge=True)
            logger.debug(f"Job {job_id}: {status} ({progress}%) - {status_message}")
    except Exception as e:
        logger.warning(f"Failed to update job {job_id} status in Firestore: {e}")

async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job from Firestore or local cache."""
    try:
        if firebase_ready():
            db = get_firestore()
            doc = db.collection('jobs').document(job_id).get()
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
    except Exception as e:
        logger.warning(f"Failed to get job {job_id} from Firestore: {e}")

    return _local_jobs.get(job_id)

async def get_user_jobs(user_id: str) -> list:
    """Get all jobs for a user from Firestore or local store."""
    jobs = []
    try:
        if firebase_ready():
            db = get_firestore()
            docs = (
                db.collection('jobs')
                .where('userId', '==', user_id)
                .order_by('createdAt', direction=firestore.Query.DESCENDING)
                .limit(50)
                .stream()
            )
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                jobs.append(data)
            return jobs
    except Exception as e:
        logger.warning(f"Failed to get jobs from Firestore for user {user_id}: {e}")

    # Fallback to local jobs
    local_list = [j for j in _local_jobs.values() if j.get('userId') == user_id]
    local_list.sort(key=lambda x: str(x.get('createdAt', '')), reverse=True)
    return local_list

def _is_bucket_usable() -> bool:
    try:
        if not firebase_ready():
            return False
        bucket = get_storage_bucket()
        return bucket.exists()
    except Exception:
        return False

async def upload_to_storage(
    local_path: str,
    storage_path: str,
    content_type: str = "audio/wav"
) -> str:
    """Upload a local file to Firebase Storage (or local storage fallback) and return download URL."""
    # Always save a local copy in local storage directory
    local_dest = os.path.join(LOCAL_STORAGE_DIR, storage_path)
    os.makedirs(os.path.dirname(local_dest), exist_ok=True)
    shutil.copy2(local_path, local_dest)

    # Try Firebase Cloud Storage if bucket is reachable
    if _is_bucket_usable():
        try:
            bucket = get_storage_bucket()
            blob = bucket.blob(storage_path)
            blob.upload_from_filename(local_path, content_type=content_type)
            download_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(hours=24),
                method="GET",
            )
            logger.info(f"Uploaded to Cloud Storage: {storage_path}")
            return download_url
        except Exception as e:
            logger.warning(f"Cloud Storage upload failed, using local URL: {e}")

    # Return relative URL served by FastAPI
    download_url = f"/api/files/{storage_path}"
    logger.info(f"Stored locally: {storage_path} -> {download_url}")
    return download_url

async def download_from_storage(storage_path: str, local_path: str):
    """Download a file from local storage or Firebase Storage to local path."""
    local_src = os.path.join(LOCAL_STORAGE_DIR, storage_path)
    if os.path.isfile(local_src):
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        shutil.copy2(local_src, local_path)
        logger.info(f"Loaded from local storage: {storage_path} -> {local_path}")
        return

    bucket = get_storage_bucket()
    blob = bucket.blob(storage_path)
    blob.download_to_filename(local_path)
    logger.info(f"Downloaded from Firebase Storage: {storage_path} -> {local_path}")

def get_signed_url(storage_path: str, expiration_minutes: int = 60) -> str:
    """Get download URL for a storage file."""
    local_src = os.path.join(LOCAL_STORAGE_DIR, storage_path)
    if os.path.isfile(local_src):
        return f"/api/files/{storage_path}"

    try:
        bucket = get_storage_bucket()
        blob = bucket.blob(storage_path)
        return blob.generate_signed_url(
            expiration=timedelta(minutes=expiration_minutes),
            method='GET',
            version='v4',
        )
    except Exception:
        return f"/api/files/{storage_path}"
