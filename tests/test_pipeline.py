"""
Comprehensive Test Suite for StemAI Audio Platform.
Tests:
- API Health & CORS
- Authentication & Security (valid, guest, invalid tokens, path traversal protection)
- Audio Upload & Validation
- Audio Analysis (BPM, key, loudness)
- Complete Demucs Separation Flow
- Vocal Mixing & Beat Synchronization
- Output File Verification
"""

import os
import sys
import time
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app
from app.config import settings
from app.services.firebase_service import init_firebase

# Ensure Firebase is initialized
init_firebase()

client = TestClient(app)

def create_synthetic_audio(duration_sec=3.0, sr=44100, freqs=(440, 880)) -> str:
    """Generate a clean multi-tone synthetic audio file for testing."""
    os.makedirs(settings.PROCESSING_TEMP_DIR, exist_ok=True)
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    sig = np.zeros_like(t)
    for f in freqs:
        sig += np.sin(2 * np.pi * f * t)
    sig = (sig / np.max(np.abs(sig)) * 0.8).astype(np.float32)
    stereo = np.column_stack([sig, sig])
    
    file_path = os.path.join(settings.PROCESSING_TEMP_DIR, f"synth_{int(time.time()*1000)}.wav")
    sf.write(file_path, stereo, sr, subtype="PCM_24")
    return file_path


def test_01_health_check():
    """Verify GET /api/health returns status ok and model information."""
    res = client.get("/api/health")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "ok"
    assert "gpu_available" in data
    assert "demucs_model" in data
    assert "version" in data


def test_02_cors_headers():
    """Verify CORS headers are present on responses."""
    res = client.options("/api/health", headers={
        "Origin": "https://stemai-frontend.vercel.app",
        "Access-Control-Request-Method": "GET"
    })
    # CORSMiddleware responds to preflight or simple requests
    res_get = client.get("/api/health", headers={"Origin": "https://stemai-frontend.vercel.app"})
    assert "access-control-allow-origin" in res_get.headers


def test_03_auth_validation():
    """Verify auth middleware rejects invalid tokens and accepts guest tokens."""
    # Missing auth
    res = client.get("/api/jobs/test_id")
    assert res.status_code == 401

    # Bad auth
    res = client.get("/api/jobs/test_id", headers={"Authorization": "Bearer bad-token-xyz"})
    assert res.status_code == 401

    # Guest token
    res = client.get("/api/jobs/nonexistent_id", headers={"Authorization": "Bearer guest-user"})
    # Should get 404 (not found) rather than 401 (unauthorized)
    assert res.status_code == 404


def test_04_upload_and_validation():
    """Test audio upload with validation."""
    audio_path = create_synthetic_audio(duration_sec=2.0)
    user_id = "guest-test-user"
    auth_header = {"Authorization": f"Bearer {user_id}"}

    try:
        # 1. Valid upload
        with open(audio_path, "rb") as f:
            res = client.post(
                "/api/upload",
                data={"user_id": user_id, "folder": "originals"},
                files={"file": ("song.wav", f, "audio/wav")},
                headers=auth_header,
            )
        assert res.status_code == 200, res.text
        upload_data = res.json()
        assert upload_data["success"] is True
        assert "storage_path" in upload_data
        assert "download_url" in upload_data
        storage_path = upload_data["storage_path"]

        # 2. Path traversal protection test
        res_traversal = client.get("/api/files/%2e%2e/%2e%2e/etc/passwd")
        assert res_traversal.status_code in [404, 400]

        # 3. Serving uploaded file
        res_file = client.get(f"/api/files/{storage_path}")
        assert res_file.status_code == 200
        assert res_file.headers["content-type"] in ["audio/wav", "audio/x-wav"]

        # 4. Invalid file rejection
        fake_file = os.path.join(settings.PROCESSING_TEMP_DIR, "fake.wav")
        with open(fake_file, "wb") as f:
            f.write(b"NOT_REAL_AUDIO_DATA_FOR_PROBING")
        with open(fake_file, "rb") as f:
            res_bad = client.post(
                "/api/upload",
                data={"user_id": user_id, "folder": "originals"},
                files={"file": ("fake.wav", f, "audio/wav")},
                headers=auth_header,
            )
        assert res_bad.status_code in [400, 422]
        if os.path.exists(fake_file):
            os.remove(fake_file)

    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


def test_05_audio_analysis():
    """Test POST /api/analyze extracts BPM, key, and structure."""
    audio_path = create_synthetic_audio(duration_sec=3.0, sr=44100, freqs=(440,))
    # Token "Bearer guest-analyzeuser" → uid = "guest-analyzeuser" (starts with "guest-", not "guest-guest-")
    # user_id = "guest-analyzeuser" → caller_uid == user_id → _is_user_authorized returns True.
    # _assert_owned_storage_path: user_id starts with "guest-" → passes immediately.
    user_id = "guest-analyzeuser"
    auth_header = {"Authorization": f"Bearer {user_id}"}

    try:
        with open(audio_path, "rb") as f:
            up_res = client.post(
                "/api/upload",
                data={"user_id": user_id, "folder": "originals"},
                files={"file": ("analyze_test.wav", f, "audio/wav")},
                headers=auth_header,
            )
        assert up_res.status_code == 200
        storage_path = up_res.json()["storage_path"]

        # Request analysis
        res = client.post(
            "/api/analyze",
            json={"storage_path": storage_path},
            headers=auth_header,
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["success"] is True
        assert "bpm" in data["analysis"]
        assert "key" in data["analysis"]
        assert "duration" in data["analysis"]
        assert data["analysis"]["duration"] > 0
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


def test_06_complete_separation_pipeline():
    """Test full separation pipeline: upload -> dispatch -> AI separate -> stems generated -> verify."""
    audio_path = create_synthetic_audio(duration_sec=2.5, sr=44100, freqs=(100, 220, 440, 880))
    user_id = "guest-sep-user"
    auth_header = {"Authorization": f"Bearer {user_id}"}
    job_id = f"job_test_sep_{int(time.time()*1000)}"

    try:
        # 1. Upload audio
        with open(audio_path, "rb") as f:
            up_res = client.post(
                "/api/upload",
                data={"user_id": user_id, "folder": "originals"},
                files={"file": ("full_track.wav", f, "audio/wav")},
                headers=auth_header,
            )
        assert up_res.status_code == 200
        storage_path = up_res.json()["storage_path"]

        # 2. Trigger separation
        sep_res = client.post(
            "/api/separate",
            json={
                "job_id": job_id,
                "user_id": user_id,
                "storage_path": storage_path,
                "model": "htdemucs",
            },
            headers=auth_header,
        )
        assert sep_res.status_code == 200, sep_res.text
        assert sep_res.json()["success"] is True

        # 3. Poll job status until complete or timeout (max 120s)
        completed = False
        start_wait = time.time()
        job_data = None

        while time.time() - start_wait < 120:
            status_res = client.get(f"/api/jobs/{job_id}", headers=auth_header)
            assert status_res.status_code == 200, status_res.text
            job_data = status_res.json().get("job", {})
            status = job_data.get("status")

            if status == "completed":
                completed = True
                break
            elif status == "failed":
                raise AssertionError(f"Separation job failed: {job_data.get('error')}")

            time.sleep(2)

        assert completed is True, f"Job timed out: status={job_data.get('status')}, progress={job_data.get('progress')}"
        assert len(job_data.get("stems", [])) >= 4, f"Expected at least 4 stems, got: {job_data.get('stems')}"

        stem_names = {s["stem"] for s in job_data["stems"]}
        for expected in ["vocals", "drums", "bass", "other", "instrumental"]:
            assert expected in stem_names, f"Missing stem: {expected}"

        # 4. Verify each stem audio is playable and non-empty
        for stem in job_data["stems"]:
            stem_url = stem["downloadUrl"]
            file_res = client.get(stem_url)
            assert file_res.status_code == 200, f"Stem {stem['stem']} failed to download from {stem_url}"
            assert len(file_res.content) > 1000, f"Stem {stem['stem']} is too small"

    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


def test_07_complete_vocal_mix_pipeline():
    """Test full vocal mix pipeline: upload vocal & inst -> mix -> verify output."""
    vocal_path = create_synthetic_audio(duration_sec=2.0, sr=44100, freqs=(440,))
    inst_path = create_synthetic_audio(duration_sec=2.0, sr=44100, freqs=(100, 220))
    user_id = "guest-mix-user"
    auth_header = {"Authorization": f"Bearer {user_id}"}
    job_id = f"job_test_mix_{int(time.time()*1000)}"

    try:
        # Upload vocal
        with open(vocal_path, "rb") as f:
            v_up = client.post(
                "/api/upload",
                data={"user_id": user_id, "folder": "vocals"},
                files={"file": ("vocal.wav", f, "audio/wav")},
                headers=auth_header,
            )
        assert v_up.status_code == 200
        vocal_storage = v_up.json()["storage_path"]

        # Upload instrumental
        with open(inst_path, "rb") as f:
            i_up = client.post(
                "/api/upload",
                data={"user_id": user_id, "folder": "instrumentals"},
                files={"file": ("inst.wav", f, "audio/wav")},
                headers=auth_header,
            )
        assert i_up.status_code == 200
        inst_storage = i_up.json()["storage_path"]

        # Trigger mix
        mix_res = client.post(
            "/api/mix",
            json={
                "job_id": job_id,
                "user_id": user_id,
                "vocal_path": vocal_storage,
                "instrumental_path": inst_storage,
                "vocal_gain": 0.85,
                "instrumental_gain": 1.0,
                "time_stretch": True,
            },
            headers=auth_header,
        )
        assert mix_res.status_code == 200, mix_res.text

        # Poll until complete
        completed = False
        start_wait = time.time()
        job_data = None

        while time.time() - start_wait < 60:
            status_res = client.get(f"/api/jobs/{job_id}", headers=auth_header)
            assert status_res.status_code == 200
            job_data = status_res.json().get("job", {})
            status = job_data.get("status")

            if status == "completed":
                completed = True
                break
            elif status == "failed":
                raise AssertionError(f"Mix job failed: {job_data.get('error')}")

            time.sleep(1)

        assert completed is True, f"Mix job timed out: status={job_data.get('status')}"
        mixed_url = job_data.get("mixedTrackUrl")
        assert mixed_url is not None

        # Verify output audio file is playable
        file_res = client.get(mixed_url)
        assert file_res.status_code == 200
        assert len(file_res.content) > 1000

    finally:
        for p in [vocal_path, inst_path]:
            if os.path.exists(p):
                os.remove(p)


if __name__ == "__main__":
    tests = [
        test_01_health_check,
        test_02_cors_headers,
        test_03_auth_validation,
        test_04_upload_and_validation,
        test_05_audio_analysis,
        test_06_complete_separation_pipeline,
        test_07_complete_vocal_mix_pipeline,
    ]
    passed = 0
    failed = 0
    print("=" * 60)
    print("RUNNING STEMAI TEST SUITE")
    print("=" * 60)
    for t in tests:
        name = t.__name__
        print(f"\n▶ Running {name}...")
        try:
            t()
            print(f"  ✓ {name} PASSED")
            passed += 1
        except Exception as e:
            print(f"  ✗ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)
