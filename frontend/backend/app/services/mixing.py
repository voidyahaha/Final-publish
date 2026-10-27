"""
Audio mixing service.
Mixes processed vocal with instrumental, normalizes and encodes.
Uses internal WAV/PCM throughout; encodes to MP3 only at output stage.
"""

import numpy as np
import soundfile as sf
import librosa
import os
import subprocess
from loguru import logger
from typing import Optional
from app.config import settings


def mix_vocal_with_instrumental(
    vocal_path: str,
    instrumental_path: str,
    output_path: str,
    vocal_gain: float = 0.85,
    instrumental_gain: float = 1.0,
) -> str:
    """
    Mix vocal with instrumental at the given gain levels.
    Normalizes output and prevents clipping.
    Output is always WAV internally; caller encodes to final format.

    Args:
        vocal_path: Path to (already time-stretched) vocal WAV
        instrumental_path: Path to instrumental WAV
        output_path: Output WAV path
        vocal_gain: 0.0–2.0 gain for vocals
        instrumental_gain: 0.0–2.0 gain for instrumental

    Returns:
        output_path
    """
    logger.info(f"Mixing: vocal_gain={vocal_gain}, inst_gain={instrumental_gain}")

    # Load both files
    y_vocal, sr_v = librosa.load(vocal_path, sr=None, mono=False)
    y_inst, sr_i = librosa.load(instrumental_path, sr=None, mono=False)

    # Resample vocal if SR differs
    target_sr = sr_i
    if sr_v != sr_i:
        logger.info(f"Resampling vocal {sr_v}Hz -> {sr_i}Hz")
        if y_vocal.ndim == 1:
            y_vocal = librosa.resample(y_vocal, orig_sr=sr_v, target_sr=sr_i)
        else:
            y_vocal = np.stack([
                librosa.resample(y_vocal[ch], orig_sr=sr_v, target_sr=sr_i)
                for ch in range(y_vocal.shape[0])
            ])

    # Convert mono to stereo if needed
    def ensure_stereo(audio: np.ndarray) -> np.ndarray:
        if audio.ndim == 1:
            return np.stack([audio, audio])
        return audio

    y_vocal = ensure_stereo(y_vocal)
    y_inst = ensure_stereo(y_inst)

    # Pad shorter track to match longer
    max_len = max(y_vocal.shape[-1], y_inst.shape[-1])

    def pad(arr: np.ndarray, length: int) -> np.ndarray:
        if arr.shape[-1] < length:
            pad_width = length - arr.shape[-1]
            if arr.ndim == 1:
                return np.pad(arr, (0, pad_width))
            else:
                return np.pad(arr, ((0, 0), (0, pad_width)))
        return arr

    y_vocal = pad(y_vocal, max_len)
    y_inst = pad(y_inst, max_len)

    # Mix with gain
    mixed = (y_vocal * vocal_gain) + (y_inst * instrumental_gain)

    # Normalize to prevent clipping
    peak = np.max(np.abs(mixed))
    if peak > 0.98:
        mixed = mixed * (0.95 / peak)
        logger.info(f"Normalized: peak was {peak:.3f}")

    # LUFS-style loudness normalization (simplified)
    mixed = normalize_loudness(mixed, target_lufs=settings.TARGET_LUFS)

    # Write WAV
    sf.write(output_path, mixed.T, target_sr, subtype='PCM_24')
    logger.info(f"Mixed output: {output_path} ({os.path.getsize(output_path)//1024}KB)")
    return output_path


def normalize_loudness(audio: np.ndarray, target_lufs: float = -14.0) -> np.ndarray:
    """Simple loudness normalization."""
    try:
        # Compute RMS
        rms = np.sqrt(np.mean(audio ** 2))
        if rms < 1e-8:
            return audio

        # Convert target LUFS to linear gain (simplified)
        import librosa
        current_db = librosa.amplitude_to_db(rms, ref=1.0)
        gain_db = target_lufs - current_db
        gain_linear = librosa.db_to_amplitude(gain_db)

        # Apply gain with ceiling
        normalized = audio * gain_linear
        peak = np.max(np.abs(normalized))
        if peak > 0.98:
            normalized = normalized * (0.95 / peak)

        return normalized
    except Exception as e:
        logger.warning(f"Loudness normalization failed: {e}, skipping")
        return audio


def encode_to_mp3(input_wav: str, output_mp3: str, bitrate: str = "320k") -> str:
    """Encode WAV to MP3 using ffmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_wav,
        "-codec:a", "libmp3lame",
        "-b:a", bitrate,
        "-write_xing", "1",
        output_mp3,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg encoding failed: {result.stderr}")
    logger.info(f"Encoded to MP3: {output_mp3}")
    return output_mp3


def encode_stem_to_mp3(input_wav: str, output_mp3: str, bitrate: str = "320k") -> str:
    """Same as encode_to_mp3 but for individual stems."""
    return encode_to_mp3(input_wav, output_mp3, bitrate)
