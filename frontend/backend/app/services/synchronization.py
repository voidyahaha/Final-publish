"""
Vocal synchronization service.
Analyzes BPM of both vocal and instrumental tracks, then time-stretches
the vocal to match the instrumental's tempo without altering pitch.
Uses librosa's phase vocoder for high-quality time-stretching.
"""

import numpy as np
import soundfile as sf
import librosa
import os
from loguru import logger
from typing import Optional, Tuple


def time_stretch_vocal(
    vocal_path: str,
    target_bpm: float,
    vocal_bpm: Optional[float],
    output_path: str,
) -> Tuple[str, float, float]:
    """
    Time-stretch the vocal to match the target BPM.
    Preserves pitch (uses librosa phase vocoder).

    Args:
        vocal_path: Path to vocal audio
        target_bpm: BPM of instrumental
        vocal_bpm: BPM of vocal (auto-detected if None)
        output_path: Where to write stretched vocal

    Returns:
        (output_path, detected_vocal_bpm, stretch_ratio)
    """
    logger.info(f"Time-stretching vocal: target_bpm={target_bpm}")

    y_vocal, sr = librosa.load(vocal_path, sr=None, mono=False)

    # Handle stereo
    if y_vocal.ndim == 1:
        y_mono = y_vocal
    else:
        y_mono = y_vocal.mean(axis=0)

    # Detect vocal BPM if not provided
    if vocal_bpm is None or vocal_bpm <= 0:
        tempo, _ = librosa.beat.beat_track(y=y_mono, sr=sr)
        vocal_bpm = float(tempo)
        logger.info(f"Detected vocal BPM: {vocal_bpm:.1f}")
    else:
        logger.info(f"Using provided vocal BPM: {vocal_bpm:.1f}")

    # Calculate stretch ratio
    if abs(vocal_bpm - target_bpm) < 1.0:
        logger.info("BPM match within 1 BPM, no stretching needed")
        # Just copy the file
        import shutil
        shutil.copy2(vocal_path, output_path)
        return output_path, vocal_bpm, 1.0

    stretch_ratio = target_bpm / vocal_bpm

    # Clamp stretch ratio to avoid extreme transformations
    stretch_ratio = max(0.5, min(2.0, stretch_ratio))
    logger.info(f"Stretch ratio: {stretch_ratio:.4f} ({vocal_bpm:.1f} -> {target_bpm:.1f} BPM)")

    # Apply time stretching with pitch preservation
    if y_vocal.ndim == 1:
        y_stretched = librosa.effects.time_stretch(y_vocal, rate=stretch_ratio)
    else:
        # Process each channel separately
        channels = []
        for ch in range(y_vocal.shape[0]):
            ch_stretched = librosa.effects.time_stretch(y_vocal[ch], rate=stretch_ratio)
            channels.append(ch_stretched)
        # Pad to equal length
        max_len = max(c.shape[0] for c in channels)
        y_stretched = np.stack([
            np.pad(c, (0, max_len - c.shape[0])) for c in channels
        ])

    # Write output
    if y_stretched.ndim == 1:
        sf.write(output_path, y_stretched, sr, subtype='PCM_24')
    else:
        sf.write(output_path, y_stretched.T, sr, subtype='PCM_24')

    logger.info(f"Time-stretch complete: {output_path}")
    return output_path, vocal_bpm, stretch_ratio


def trim_silence(audio: np.ndarray, sr: int, top_db: int = 40) -> np.ndarray:
    """Trim leading/trailing silence from audio."""
    if audio.ndim == 1:
        trimmed, _ = librosa.effects.trim(audio, top_db=top_db)
        return trimmed
    else:
        # Trim based on mono
        mono = audio.mean(axis=0) if audio.ndim == 2 else audio
        _, index = librosa.effects.trim(mono, top_db=top_db)
        return audio[:, index[0]:index[1]] if audio.ndim == 2 else audio[index[0]:index[1]]


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

    y_inst, sr_inst = librosa.load(instrumental_path, sr=None, mono=True)
    _, beat_frames = librosa.beat.beat_track(y=y_inst, sr=sr_inst)

    if len(beat_frames) > 0:
        first_beat_time = librosa.frames_to_time(beat_frames[0], sr=sr_inst)
        logger.info(f"First beat at {first_beat_time:.3f}s")
    else:
        first_beat_time = 0.0
        logger.info("No beats detected, starting at 0s")

    y_vocal, sr_vocal = librosa.load(vocal_path, sr=None, mono=False)

    # Resample if needed
    if sr_vocal != sr_inst:
        if y_vocal.ndim == 1:
            y_vocal = librosa.resample(y_vocal, orig_sr=sr_vocal, target_sr=sr_inst)
        else:
            y_vocal = np.stack([
                librosa.resample(y_vocal[i], orig_sr=sr_vocal, target_sr=sr_inst)
                for i in range(y_vocal.shape[0])
            ])
        sr_vocal = sr_inst

    # Add silence padding
    silence_samples = int(first_beat_time * sr_vocal)
    if silence_samples > 0:
        if y_vocal.ndim == 1:
            silence = np.zeros(silence_samples)
            y_vocal = np.concatenate([silence, y_vocal])
        else:
            silence = np.zeros((y_vocal.shape[0], silence_samples))
            y_vocal = np.concatenate([silence, y_vocal], axis=1)

    if y_vocal.ndim == 1:
        sf.write(output_path, y_vocal, sr_vocal, subtype='PCM_24')
    else:
        sf.write(output_path, y_vocal.T, sr_vocal, subtype='PCM_24')

    logger.info(f"Aligned vocal written to {output_path}")
    return output_path
