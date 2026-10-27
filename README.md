# Sonder Audio Studio

A real audio application: HTDemucs-Fine-Tuned four-stem separation, beat/BPM analysis, pitch-preserving vocal tempo alignment, instrumental reconstruction, peak-safe mixing, and WAV/320 kbps MP3 delivery.

## Deployment model

Vercel serves the static frontend; it is not appropriate for long PyTorch/Demucs jobs. Run FastAPI on a persistent CPU/GPU host with persistent scratch storage. Firebase Auth, Firestore, and Cloud Storage provide authentication and durable metadata/audio. Included deployment templates are starters, not deployed cloud resources.

## Local setup

Requires Python 3.10–3.12, FFmpeg/ffprobe, PyTorch-compatible hardware, and disk/RAM for WAV intermediates. CPU processing works but is slower. On first job, Demucs downloads `htdemucs_ft` weights; model files are intentionally excluded.

```sh
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# For local-only development, leave FIREBASE_STORAGE_BUCKET blank.
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Run the Vite frontend with `cd frontend && npm ci && npm run dev`. Set `VITE_API_URL` to the FastAPI origin when hosted on another domain (or use the Vite proxy locally). Production CORS must list the exact site origin.

## Firebase production setup

1. Enable Email/Password and Google Authentication providers, then create Firestore/Storage.
2. Deploy `firestore.rules` and `storage.rules` with Firebase CLI.
3. Mount a least-privilege Firebase service account as a host secret and set `GOOGLE_APPLICATION_CREDENTIALS` (or set the complete JSON in the secret `FIREBASE_SERVICE_ACCOUNT_JSON`) plus `FIREBASE_STORAGE_BUCKET`. Never commit the key. The Admin SDK verifies Firebase ID tokens.
4. Deploy `frontend/` to Vercel and the API container separately; configure API URL, CORS, and service-account secret. Admin SDK writes generated files and job records; client cannot forge job state.

The Firebase Web API key is a public client identifier, not a server secret. Browser anonymous auth is enabled in the design. Original uploads and generated assets are stored under owner-scoped paths. Local mode is supported without Firebase. Temporary Demucs work files are removed on success; failed job files remain for diagnosis and should be covered by host retention/cleanup policies.

## API

- `GET /api/health` — service and model status.
- `POST /api/jobs` — multipart `audio`, optional `vocal`, and `kind=separate|mix|separate-and-mix`.
- `GET /api/jobs/{id}` — status/stage, error, analysis and artifact references.
- `GET /api/jobs/{id}/download/{asset}` — authenticated fresh signed URL for a stem or `mixed` output.
- `GET /api/jobs/{id}/files/{name}` — verified playback/download: `vocals`, `drums`, `bass`, `other`, `instrumental`, `final-wav`, `final-mp3`.

The upload has actual browser progress, validates format/size, and shows API errors. Job stages move through queued, processing, separating/mixing, then completed/failed. Outputs are only marked complete after files are generated, verified, and stored.

## Processing details and limitations

`htdemucs_ft` produces vocals/drums/bass/other. The instrumental is the sum of drums, bass, and other, not EQ or center-channel cancellation. `librosa` estimates tempo/onset; moderate tempo ratios are pitch-preserving time-stretched and vocal onset is shifted to the first detected instrumental beat. A peak-safe mix is encoded to 24-bit WAV and 320 kbps MP3. Beat detection is heuristic and may not find musical phrase alignment for free-time/live audio.

This uses an in-process job runner plus Firestore status persistence. Run one API process per instance; in-memory execution cannot resume a job after a host crash. Production horizontal scaling/crash durability needs a managed task queue (Cloud Tasks/Celery/Redis) and lease recovery. Configure request timeouts and disk cleanup appropriate to your host. Default limit: 250 MB, 30 minutes.

The repository does not include FFmpeg, Firebase Admin credentials, Demucs weights, or GPU resources. Run the verification checklist below on the deployed API with credentials and a representative track before accepting production traffic.

## Verification checklist

1. `GET /api/health` reports the expected model and GPU state.
2. Sign in from the frontend, upload an MP3/WAV/FLAC/M4A file, and confirm Firebase Storage contains the owner-scoped original.
3. Start a separation and observe `queued → processing → separating → completed` in Firestore and the UI.
4. Play and download every returned stem; verify the files are non-empty and have distinct audio content.
5. Record or upload a vocal, upload an instrumental, and verify the mixer reports BPMs and produces a playable 320 kbps MP3.
6. Retry a bad file and confirm the UI shows the backend error and the job is `failed`, never falsely `completed`.

## ZIP

The project archive excludes weights, node_modules, virtual environments, caches, and generated audio.
`AI-Audio-Platform.zip` is written at the repository root and copied to
`storage/shared/android/codex/AI-Audio-Platform.zip` when that Termux shared-storage path is available.
# Final-publish
