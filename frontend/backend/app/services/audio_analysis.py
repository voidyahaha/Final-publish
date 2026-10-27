"""
Audio analysis service.
Uses librosa for BPM, beats, key, onsets and loudness analysis.
"""

import numpy as np
import soundfile as sf
import librosa
import os
from loguru import logger
from typing import Dict, Any, Optional


def analyze_audio(file_path: str) -> Dict[str, Any]:
    """
    Perform comprehensive audio analysis.

    Returns:
        Dict with bpm, key, duration, sample_rate, loudness, beats, onsets
    """
    logger.info(f"Analyzing audio: {file_path}")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    try:
        # Load audio for analysis (mono, standard sample rate)
        y, sr = librosa.load(file_path, sr=None, mono=True)

        # Duration
        duration = librosa.get_duration(y=y, sr=sr)

        # BPM and beat frames
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, tightness=100)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
        bpm = float(tempo)

        # More accurate BPM using plp
        try:
            pulse = librosa.beat.plp(y=y, sr=sr)
            plp_tempo = librosa.tempo(tg=pulse, sr=sr, ac_size=8.0)
            if len(plp_tempo) > 0 and 60 <= float(plp_tempo[0]) <= 240:
                bpm = float(plp_tempo[0])
        except Exception:
            pass  # Fall back to beat_track result

        # Onset detection
        onset_frames = librosa.onset.onset_detect(y=y, sr=sr)
        onset_times = librosa.frames_to_time(onset_frames, sr=sr).tolist()

        # Key detection using chroma features
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_mean = chroma.mean(axis=1)
        key_idx = int(np.argmax(chroma_mean))
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        detected_key = note_names[key_idx]

        # Determine major/minor using harmonic profile
        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

        from scipy.stats import pearsonr
        major_corr, _ = pearsonr(chroma_mean, np.roll(major_profile, key_idx))
        minor_corr, _ = pearsonr(chroma_mean, np.roll(minor_profile, key_idx))
        mode = "major" if major_corr > minor_corr else "minor"
        detected_key_full = f"{detected_key} {mode}"

        # RMS loudness
        rms = librosa.feature.rms(y=y)[0]
        rms_db = float(librosa.amplitude_to_db(np.mean(rms)))

        logger.info(f"Analysis done: bpm={bpm:.1f}, key={detected_key_full}, duration={duration:.1f}s")

        return {
            "bpm": round(bpm, 2),
            "key": detected_key_full,
            "duration": round(duration, 3),
            "sample_rate": int(sr),
            "loudness": round(rms_db, 2),
            "beats": [round(t, 3) for t in beat_times[:200]],  # Limit for response size
            "onsets": [round(t, 3) for t in onset_times[:200]],
        }

    except Exception as e:
        logger.exception(f"Audio analysis failed: {e}")
        raise RuntimeError(f"Audio analysis failed: {str(e)}")


def get_bpm_and_beats(file_path: str):
    """Quick BPM and beat extraction."""
    y, sr = librosa.load(file_path, sr=None, mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    return float(tempo), beat_times.tolist(), int(sr)
