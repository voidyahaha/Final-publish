"""
Vocal synchronization service.
Analyzes BPM of both vocal and instrumental tracks, then time-stretches
the vocal to match the instrumental's tempo without altering pitch.
Uses librosa phase vocoder with FFmpeg atempo fallback.
"""

import numpy as np
import soundfile as sf
import os
import shutil
import subprocess
from loguru import logger
from typing import Optional, Tuple
from app.services.audio_analysis import get_bpm_and_beats


def _time_stretch_ffmpeg(vocal_path: str, stretch_ratio: float, output_path: str) -> str:
    """Time-stretch audio using FFmpeg's built-in atempo filter (pitch-preserving)."""
    # atempo accepts values between 0.5 and 2.0. If outside, chain filters.
    filters = []
    ratio = stretch_ratio
    while ratio > 2.0:
        filters.append("atempo=2.0")
        ratio /= 2.0
    while ratio < 0.5:
        filters.append("atempo=0.5")
        ratio /= 0.5
    filters.append(f"atempo={ratio:.4f}")
    filter_str = ",".join(filters)

    cmd = [
        "ffmpeg", "-y",
        "-i", vocal_path,
        "-filter:a", filter_str,
        "-c:a", "pcm_s24le",
        output_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg time-stretch failed: {res.stderr}")
    return output_path


def time_stretch_vocal(
    vocal_path: str,
    target_bpm: float,
    vocal_bpm: Optional[float],
    output_path: str,
) -> Tuple[str, float, float]:
    """
    Time-stretch the vocal to match the target BPM.
    Preserves pitch.

    Args:
        vocal_path: Path to vocal audio
        target_bpm: BPM of instrumental
        vocal_bpm: BPM of vocal (auto-detected if None)
        output_path: Where to write stretched vocal

    Returns:
        (output_path, detected_vocal_bpm, stretch_ratio)
    """
    logger.info(f"Time-stretching vocal: target_bpm={target_bpm}")

    # Detect vocal BPM if not provided
    if vocal_bpm is None or vocal_bpm <= 0:
        vocal_bpm, _, _ = get_bpm_and_beats(vocal_path)
        logger.info(f"Detected vocal BPM: {vocal_bpm:.1f}")
    else:
        logger.info(f"Using provided vocal BPM: {vocal_bpm:.1f}")

    # Calculate stretch ratio
    if abs(vocal_bpm - target_bpm) < 1.0:
        logger.info("BPM match within 1 BPM, no stretching needed")
        shutil.copy2(vocal_path, output_path)
        return output_path, vocal_bpm, 1.0

    stretch_ratio = target_bpm / vocal_bpm
    stretch_ratio = max(0.5, min(2.0, stretch_ratio))
    logger.info(f"Stretch ratio: {stretch_ratio:.4f} ({vocal_bpm:.1f} -> {target_bpm:.1f} BPM)")

    try:
        import librosa
        y_vocal, sr = librosa.load(vocal_path, sr=None, mono=False)
        if y_vocal.ndim == 1:
            y_stretched = librosa.effects.time_stretch(y_vocal, rate=stretch_ratio)
        else:
            channels = [librosa.effects.time_stretch(y_vocal[ch], rate=stretch_ratio) for ch in range(y_vocal.shape[0])]
            max_len = max(c.shape[0] for c in channels)
            y_stretched = np.stack([np.pad(c, (0, max_len - c.shape[0])) for c in channels])

        if y_stretched.ndim == 1:
            sf.write(output_path, y_stretched, sr, subtype='PCM_24')
        else:
            sf.write(output_path, y_stretched.T, sr, subtype='PCM_24')
    except Exception as e:
        logger.warning(f"Librosa time_stretch unavailable ({e}); using FFmpeg atempo fallback")
        _time_stretch_ffmpeg(vocal_path, stretch_ratio, output_path)

    logger.info(f"Time-stretch complete: {output_path}")
    return output_path, vocal_bpm, stretch_ratio


def align_vocals_to_first_beat(
    vocal_path: str,
    instrumental_path: str,
    output_path: str,
) -> str:
    """
    Detect first beat in instrumental and prepend silence to vocal
    so the vocal starts at the first beat.
    """
    logger.info("Aligning vocal to instrumental first beat...")

    try:
        _, beats, sr_inst = get_bpm_and_beats(instrumental_path)
        first_beat_time = beats[0] if len(beats) > 0 else 0.0
    except Exception:
        first_beat_time = 0.0

    logger.info(f"First beat at {first_beat_time:.3f}s")

    data_vocal, sr_vocal = sf.read(vocal_path)
    data_inst, sr_inst = sf.read(instrumental_path)

    # Resample if needed using ffmpeg
    if sr_vocal != sr_inst:
        resampled_tmp = output_path + ".resampled.wav"
        cmd = ["ffmpeg", "-y", "-i", vocal_path, "-ar", str(sr_inst), "-c:a", "pcm_s24le", resampled_tmp]
        subprocess.run(cmd, check=True, capture_output=True)
        data_vocal, sr_vocal = sf.read(resampled_tmp)
        if os.path.exists(resampled_tmp):
            os.remove(resampled_tmp)

    silence_samples = int(first_beat_time * sr_vocal)
    if silence_samples > 0:
        if data_vocal.ndim == 1:
            silence = np.zeros(silence_samples)
            aligned = np.concatenate([silence, data_vocal])
        else:
            silence = np.zeros((silence_samples, data_vocal.shape[1]))
            aligned = np.concatenate([silence, data_vocal], axis=0)
    else:
        aligned = data_vocal

    sf.write(output_path, aligned, sr_vocal, subtype='PCM_24')
    logger.info(f"Aligned vocal written to {output_path}")
    return output_path

