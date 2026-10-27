"""
Demucs stem separation service.
Uses HTDemucs/HTDemucs FT for highest quality separation.
Never pretends to have separated anything — verifies output files exist before reporting success.
"""

import os
import shutil
import torch
from pathlib import Path
from loguru import logger
from typing import Callable, Optional, Dict, List
import time

from app.config import settings

# Detect hardware
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
GPU_AVAILABLE = torch.cuda.is_available()

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
    model_name: str = "htdemucs_ft",
    on_progress: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, str]:
    """
    Separate audio into stems using Demucs.

    Args:
        input_path: Path to input audio file
        output_dir: Directory to save separated stems
        model_name: Demucs model name
        on_progress: Callback(percent, message)

    Returns:
        Dict mapping stem name -> output file path
    """
    from demucs.apply import apply_model, BagOfModels
    from demucs.audio import AudioFile, save_audio
    from demucs.pretrained import get_model
    import torchaudio

    logger.info(f"Starting separation: model={model_name}, device={DEVICE}")
    logger.info(f"Input: {input_path}")
    logger.info(f"Output dir: {output_dir}")

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    os.makedirs(output_dir, exist_ok=True)

    start_time = time.time()

    try:
        # Load model
        if on_progress:
            on_progress(5, f"Loading {model_name} model...")

        logger.info(f"Loading Demucs model: {model_name}")
        model = get_model(model_name)
        model.to(DEVICE)
        model.eval()
        logger.info(f"Model loaded in {time.time() - start_time:.1f}s")

        if on_progress:
            on_progress(15, "Loading audio file...")

        # Load audio
        wav = AudioFile(input_path).read(
            streams=0,
            samplerate=model.samplerate,
            channels=model.audio_channels,
        )

        # wav shape: (channels, samples)
        ref = wav.mean(0)
        wav = (wav - ref.mean()) / ref.std()
        wav = wav.unsqueeze(0)  # Add batch dim: (1, channels, samples)

        logger.info(f"Audio loaded: shape={wav.shape}, sr={model.samplerate}")

        if on_progress:
            on_progress(25, "Separating stems with AI (this takes a while)...")

        # Run separation
        with torch.no_grad():
            if isinstance(model, BagOfModels):
                # Multiple models — track progress per model
                sources = apply_model(
                    model,
                    wav,
                    device=DEVICE,
                    shifts=settings.DEMUCS_SHIFTS,
                    split=True,
                    overlap=settings.DEMUCS_OVERLAP,
                    progress=True,
                    num_workers=0,
                )
            else:
                sources = apply_model(
                    model,
                    wav,
                    device=DEVICE,
                    shifts=settings.DEMUCS_SHIFTS,
                    split=True,
                    overlap=settings.DEMUCS_OVERLAP,
                    progress=True,
                )

        logger.info(f"Separation completed in {time.time() - start_time:.1f}s")

        if on_progress:
            on_progress(80, "Saving stem files...")

        # Denormalize
        sources = sources * ref.std() + ref.mean()

        # Save each stem
        stem_names = model.sources
        output_files = {}

        for i, stem_name in enumerate(stem_names):
            stem_audio = sources[0, i]  # Remove batch dim
            output_path = os.path.join(output_dir, f"{stem_name}.wav")

            save_audio(
                stem_audio.cpu(),
                output_path,
                samplerate=model.samplerate,
            )

            if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
                raise RuntimeError(f"Stem file missing or empty: {output_path}")

            output_files[stem_name] = output_path
            logger.info(f"Saved stem: {stem_name} -> {output_path} ({os.path.getsize(output_path)//1024}KB)")

        # Generate instrumental = sum of all non-vocal stems
        if "vocals" in output_files and len(output_files) > 1:
            if on_progress:
                on_progress(88, "Generating instrumental mix...")

            import torchaudio
            import torch

            non_vocal_sources = [
                sources[0, i]
                for i, name in enumerate(stem_names)
                if name != "vocals"
            ]
            if non_vocal_sources:
                instrumental = torch.stack(non_vocal_sources).sum(0)
                instrumental_path = os.path.join(output_dir, "instrumental.wav")
                save_audio(instrumental.cpu(), instrumental_path, samplerate=model.samplerate)
                output_files["instrumental"] = instrumental_path
                logger.info(f"Generated instrumental: {instrumental_path}")

        if on_progress:
            on_progress(95, "Stems ready, uploading...")

        total_time = time.time() - start_time
        logger.info(f"Separation complete in {total_time:.1f}s. Files: {list(output_files.keys())}")

        return output_files

    except Exception as e:
        logger.exception(f"Separation failed: {e}")
        raise RuntimeError(f"Demucs separation failed: {str(e)}")


def get_stem_info(stem_path: str) -> Dict:
    """Get audio file metadata."""
    import soundfile as sf
    try:
        info = sf.info(stem_path)
        return {
            "duration": info.duration,
            "sample_rate": info.samplerate,
            "size_bytes": os.path.getsize(stem_path),
        }
    except Exception as e:
        logger.warning(f"Could not get stem info for {stem_path}: {e}")
        return {"duration": None, "sample_rate": None, "size_bytes": os.path.getsize(stem_path)}
