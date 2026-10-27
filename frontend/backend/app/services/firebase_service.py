import firebase_admin
from firebase_admin import credentials, firestore, storage as fb_storage
from app.config import settings
from loguru import logger
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any

_firebase_app = None

def init_firebase():
    """Initialize Firebase Admin SDK."""
    global _firebase_app
    if _firebase_app:
        return _firebase_app

    try:
        cred_path = settings.FIREBASE_CREDENTIALS_PATH

        if cred_path and os.path.exists(cred_path):
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
    return firestore.client()

def get_storage_bucket():
    """Get Firebase Storage bucket."""
    return fb_storage.bucket()

async def update_job_status(
    job_id: str,
    status: str,
    progress: int,
    status_message: str,
    extra: Optional[Dict[str, Any]] = None
):
    """Update job status in Firestore."""
    try:
        db = get_firestore()
        update_data = {
            'status': status,
            'progress': progress,
            'statusMessage': status_message,
            'updatedAt': firestore.SERVER_TIMESTAMP,
        }
        if extra:
            update_data.update(extra)

        if status == 'completed':
            update_data['completedAt'] = firestore.SERVER_TIMESTAMP

        db.collection('jobs').document(job_id).update(update_data)
        logger.debug(f"Job {job_id}: {status} ({progress}%) - {status_message}")
    except Exception as e:
        logger.error(f"Failed to update job {job_id} status: {e}")

async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job from Firestore."""
    try:
        db = get_firestore()
        doc = db.collection('jobs').document(job_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e}")
        return None

async def get_user_jobs(user_id: str) -> list:
    """Get all jobs for a user."""
    try:
        db = get_firestore()
        docs = (
            db.collection('jobs')
            .where('userId', '==', user_id)
            .order_by('createdAt', direction=firestore.Query.DESCENDING)
            .limit(50)
            .stream()
        )
        jobs = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            jobs.append(data)
        return jobs
    except Exception as e:
        logger.error(f"Failed to get jobs for user {user_id}: {e}")
        return []

async def upload_to_storage(
    local_path: str,
    storage_path: str,
    content_type: str = "audio/wav"
) -> str:
    """Upload a local file to Firebase Storage and return download URL."""
    bucket = get_storage_bucket()
    blob = bucket.blob(storage_path)
    blob.upload_from_filename(local_path, content_type=content_type)
    blob.make_public()
    download_url = blob.public_url
    logger.info(f"Uploaded {local_path} -> {storage_path}")
    return download_url

async def download_from_storage(storage_path: str, local_path: str):
    """Download a file from Firebase Storage to local path."""
    bucket = get_storage_bucket()
    blob = bucket.blob(storage_path)
    blob.download_to_filename(local_path)
    logger.info(f"Downloaded {storage_path} -> {local_path}")

def get_signed_url(storage_path: str, expiration_minutes: int = 60) -> str:
    """Get a signed URL for a private storage file."""
    import datetime
    bucket = get_storage_bucket()
    blob = bucket.blob(storage_path)
    url = blob.generate_signed_url(
        expiration=datetime.timedelta(minutes=expiration_minutes),
        method='GET',
        version='v4',
    )
    return url
