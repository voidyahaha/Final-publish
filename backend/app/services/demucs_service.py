"""
Demucs stem separation service.
Optimized for low-resource cloud CPUs (Render Free Tier: 512MB RAM, 1 CPU).
Uses lightweight single-thread chunking and segmenting to prevent memory kill.
"""

import os
import shutil
import torch
from pathlib import Path
from loguru import logger
from typing import Callable, Optional, Dict, List
import time

from app.config import settings

# Force CPU inference on cloud web tier
DEVICE = "cpu"
GPU_AVAILABLE = False

logger.info(f"Demucs: device={DEVICE}, GPU={GPU_AVAILABLE}")

STEM_MAP = {
    "htdemucs": ["vocals", "drums", "bass", "other"],
    "htdemucs_ft": ["vocals", "drums", "bass", "other"],
    "mdx_extra": ["vocals", "drums", "bass", "other"],
    "htdemucs_6s": ["vocals", "drums", "bass", "other", "piano", "guitar"],
}

def get_available_stems(model_name: str) -> List[str]:
    return STEM_MAP.get(model_name, ["vocals", "drums", "bass", "other"])

def separate_audio(
    input_path: str,
    output_dir: str,
    model_name: str = "htdemucs",
    on_progress: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, str]:
    """Separate audio into stems using Demucs."""
    from demucs.apply import apply_model
    from demucs.audio import AudioFile, save_audio
    from demucs.pretrained import get_model

    # On free CPU tier, force the lightweight base model
    model_name = "htdemucs"
    logger.info(f"Starting separation: model={model_name}, device={DEVICE}, input={input_path}")

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    os.makedirs(output_dir, exist_ok=True)
    start_time = time.time()

    try:
        if on_progress:
            on_progress(20, "Loading AI model weights...")

        model = get_model(model_name)
        model.to(DEVICE)
        model.eval()

        if on_progress:
            on_progress(25, "Reading and normalizing audio...")

        wav = AudioFile(input_path).read(
            streams=0,
            samplerate=model.samplerate,
            channels=model.audio_channels,
        )

        ref = wav.mean(0)
        ref_std = ref.std().clamp_min(1e-8)
        wav = (wav - ref.mean()) / ref_std
        wav = wav.unsqueeze(0)

        total_samples = wav.shape[-1]
        logger.info(f"Audio loaded: shape={wav.shape}, sr={model.samplerate}")

        if on_progress:
            on_progress(30, "AI separating stems (30%)...")

        last_reported_pct = [30]
        last_reported_time = [time.time()]

        def chunk_progress_callback(d):
            offset = d.get("segment_offset", 0)
            model_idx = d.get("model_idx_in_bag", 0)
            num_models = d.get("models", 1)
            chunk_ratio = min(1.0, max(0.0, offset / max(1, total_samples)))
            overall_ratio = (model_idx + chunk_ratio) / max(1, num_models)
            pct = int(30 + overall_ratio * 50)  # progress 30% to 80%
            now = time.time()
            if pct > last_reported_pct[0] and (now - last_reported_time[0] >= 1.5 or pct >= last_reported_pct[0] + 3):
                last_reported_pct[0] = pct
                last_reported_time[0] = now
                if on_progress:
                    on_progress(pct, f"AI separating stems ({pct}%)...")

        # Set single thread to avoid memory thrashing on 512MB RAM
        torch.set_num_threads(1)

        with torch.inference_mode():
            sources = apply_model(
                model,
                wav,
                device=DEVICE,
                shifts=0,
                split=True,
                overlap=0.0,
                progress=False,
                callback=chunk_progress_callback,
            )

        logger.info(f"Separation completed in {time.time() - start_time:.1f}s")

        if on_progress:
            on_progress(82, "Saving isolated stems to disk...")

        # Denormalize
        sources = sources * ref_std + ref.mean()
        stem_names = model.sources
        stem_files = {}

        for i, name in enumerate(stem_names):
            stem_path = os.path.join(output_dir, f"{name}.wav")
            save_audio(
                sources[0, i],
                stem_path,
                samplerate=model.samplerate,
                bitrate=320,
                clip="rescale",
                as_float=False,
            )
            stem_files[name] = stem_path

        # Generate instrumental stem by summing non-vocal stems
        if "vocals" in stem_files:
            inst_path = os.path.join(output_dir, "instrumental.wav")
            inst_idx = [i for i, name in enumerate(stem_names) if name != "vocals"]
            if inst_idx:
                inst_audio = sources[0, inst_idx].sum(0)
                save_audio(
                    inst_audio,
                    inst_path,
                    samplerate=model.samplerate,
                    bitrate=320,
                    clip="rescale",
                    as_float=False,
                )
                stem_files["instrumental"] = inst_path

        return stem_files

    finally:
        # Free memory aggressively
        del wav
        try:
            del sources
        except Exception:
            pass
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def get_stem_info(path: str) -> Dict:
    """Return duration, sample rate, channels for a given audio file."""
    import soundfile as sf
    try:
        info = sf.info(path)
        return {
            "duration": round(info.duration, 2),
            "sample_rate": info.samplerate,
            "channels": info.channels,
            "format": info.format,
        }
    except Exception as e:
        logger.warning(f"Could not read audio info for {path}: {e}")
        return {"duration": 0, "sample_rate": 44100, "channels": 2, "format": "UNKNOWN"}
