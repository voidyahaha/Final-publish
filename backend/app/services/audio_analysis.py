"""
Audio analysis service.
Uses librosa for BPM, beats, key, onsets and loudness analysis,
with scipy/soundfile fallback when librosa/numba is unavailable.
"""

import numpy as np
import soundfile as sf
import os
from loguru import logger
from typing import Dict, Any, Optional, Tuple, List


def _fallback_analysis(file_path: str) -> Dict[str, Any]:
    """Fallback audio analysis using soundfile and scipy."""
    from scipy.signal import find_peaks

    data, sr = sf.read(file_path)
    y = data.mean(axis=1) if data.ndim > 1 else data
    duration = float(len(y) / sr)
    rms = float(np.sqrt(np.mean(y ** 2)))
    loudness = float(20 * np.log10(max(rms, 1e-9)))

    # Onset detection via energy envelope derivative
    hop_size = 512
    num_hops = len(y) // hop_size
    if num_hops > 1:
        frames = y[:num_hops * hop_size].reshape(num_hops, hop_size)
        energy = np.sum(frames ** 2, axis=1)
        energy_diff = np.diff(energy, prepend=0)
        energy_diff[energy_diff < 0] = 0
        min_dist = max(1, int(0.2 * sr / hop_size))
        peaks, _ = find_peaks(energy_diff, distance=min_dist, prominence=np.max(energy_diff) * 0.1 if np.max(energy_diff) > 0 else None)
        onset_times = [round(float(p * hop_size / sr), 3) for p in peaks]
    else:
        onset_times = []

    # Estimate BPM from onset intervals
    if len(onset_times) >= 4:
        diffs = np.diff(onset_times)
        diffs = diffs[(diffs >= 0.25) & (diffs <= 1.5)]  # 40 - 240 BPM
        if len(diffs) > 0:
            median_interval = float(np.median(diffs))
            bpm = round(60.0 / median_interval, 2)
            beats = [round(t, 3) for t in onset_times[:200]]
        else:
            bpm = 120.0
            beats = []
    else:
        bpm = 120.0
        beats = []

    # Chroma / Key detection using FFT
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    try:
        n_fft = min(len(y), 16384)
        if n_fft >= 2048:
            spec = np.abs(np.fft.rfft(y[:n_fft]))
            freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
            # Map frequencies to chromatic pitch classes (A4 = 440)
            valid = freqs > 27.5
            freqs_v = freqs[valid]
            spec_v = spec[valid]
            midi = 12 * np.log2(freqs_v / 440.0) + 69
            pitch_classes = (np.round(midi).astype(int)) % 12
            chroma = np.zeros(12)
            for pc in range(12):
                chroma[pc] = np.sum(spec_v[pitch_classes == pc])
            key_idx = int(np.argmax(chroma))
            detected_key = f"{note_names[key_idx]} major"
        else:
            detected_key = "C major"
    except Exception:
        detected_key = "C major"

    return {
        "bpm": bpm,
        "key": detected_key,
        "duration": round(duration, 3),
        "sample_rate": int(sr),
        "loudness": round(loudness, 2),
        "beats": beats,
        "onsets": onset_times[:200],
    }


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
        import librosa
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
        logger.warning(f"Librosa analysis unavailable ({e}); using scipy fallback")
        try:
            return _fallback_analysis(file_path)
        except Exception as fb_err:
            logger.exception(f"Audio analysis failed: {fb_err}")
            raise RuntimeError(f"Audio analysis failed: {str(fb_err)}")


def get_bpm_and_beats(file_path: str):
    """Quick BPM and beat extraction."""
    try:
        import librosa
        y, sr = librosa.load(file_path, sr=None, mono=True)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        return float(tempo), beat_times.tolist(), int(sr)
    except Exception:
        res = _fallback_analysis(file_path)
        return float(res["bpm"]), res["beats"], int(res["sample_rate"])

