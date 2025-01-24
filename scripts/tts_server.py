#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fastapi>=0.109.0",
#   "uvicorn>=0.27.0",
#   "torch>=2.1.0",
#   "transformers>=4.36.0",
#   "scipy>=1.11.0",
#   "munch>=4.0.0",
#   "phonemizer>=3.2.0",
# ]
# ///
"""
Simple TTS server using Kokoro TTS.

Usage:
    ./tts_server.py

API Endpoints:
    GET /tts?text=Hello - Convert text to speech
    GET /health - Check server health
"""

import glob
import io
import logging
import shutil
import sys
from pathlib import Path

import click
import numpy as np
import scipy.io.wavfile as wavfile
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from phonemizer.backend.espeak.wrapper import EspeakWrapper

script_dir = Path(__file__).parent

# Add Kokoro-82M to Python path
kokoro_path = (script_dir / "Kokoro-82M").absolute()
sys.path.insert(0, str(kokoro_path))

# on macOS, use workaround for espeak detection
if sys.platform == "darwin":
    # Find espeak library using glob
    espeak_libs = glob.glob("/opt/homebrew/Cellar/espeak/*/lib/libespeak.*.dylib")
    if not espeak_libs:
        raise RuntimeError(
            "Could not find espeak library in Homebrew. Please install it with 'brew install espeak'"
        )
    _ESPEAK_LIBRARY = espeak_libs[0]  # Use the first match
    EspeakWrapper.set_library(_ESPEAK_LIBRARY)

from kokoro import generate  # fmt: skip
from models import build_model  # fmt: skip

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="TTS Server")

# Global variables for model and voicepack
MODEL = None
VOICEPACK = None
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DEFAULT_VOICE = None


def _list_voices():
    """List all available voice files."""
    voice_dir = kokoro_path / "voices"
    voices = glob.glob(str(voice_dir / "*.pt"))
    return [Path(v).stem for v in voices]


def load_voice(voice_name: str):
    """Load a specific voice by name."""
    voice_path = kokoro_path / "voices" / f"{voice_name}.pt"
    if not voice_path.exists():
        raise ValueError(f"Voice {voice_name} not found")
    return torch.load(voice_path, weights_only=True).to(DEVICE)


def _check_espeak():
    if not any([shutil.which("espeak"), shutil.which("espeak-ng")]):
        raise RuntimeError(
            "Failed to find `espeak` or `espeak-ng`. Try to install it using 'sudo apt-get install espeak-ng' or equivalent"
        ) from None


def init_model(voice: str | None = None):
    """Initialize the Kokoro TTS model and voicepack."""
    global MODEL, VOICEPACK, DEFAULT_VOICE

    try:
        _check_espeak()

        log.info("Loading model...")
        MODEL = build_model(str(kokoro_path / "kokoro-v0_19.pth"), DEVICE)

        log.info("Loading voicepack...")
        available_voices = _list_voices()
        if not available_voices:
            raise RuntimeError("No voice files found")

        # Use specified voice or default "af"
        voice_name = voice or "af"
        if voice_name not in available_voices:
            raise ValueError(
                f"Voice {voice_name} not found. Available voices: {available_voices}"
            )

        DEFAULT_VOICE = voice_name
        VOICEPACK = load_voice(voice_name)
        log.info(f"Model initialization complete (using voice: {voice_name})")

    except Exception as e:
        log.error(f"Failed to initialize model: {e}")
        raise


def strip_silence(
    audio_data: np.ndarray,
    threshold: float = 0.01,
    min_silence_duration: int = 1000,
) -> np.ndarray:
    """Strip silence from the beginning and end of audio data.

    Args:
        audio_data: Audio data as numpy array
        threshold: Amplitude threshold below which is considered silence
        min_silence_duration: Minimum silence duration in samples
    """
    # Convert to absolute values
    abs_audio = np.abs(audio_data)

    # Find indices where audio is above threshold
    mask = abs_audio > threshold

    # Find first and last non-silent points
    non_silent = np.where(mask)[0]
    if len(non_silent) == 0:
        return audio_data

    start = max(0, non_silent[0] - min_silence_duration)
    end = min(len(audio_data), non_silent[-1] + min_silence_duration)

    return audio_data[start:end]


@app.on_event("startup")
async def startup_event():
    """Initialize model on startup."""
    init_model(DEFAULT_VOICE)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model_loaded": MODEL is not None,
        "voicepack_loaded": VOICEPACK is not None,
        "default_voice": DEFAULT_VOICE,
        "available_voices": _list_voices(),
        "device": DEVICE,
    }


@app.get("/tts")
async def text_to_speech(text: str, speed: float = 1.0, voice: str | None = None):
    """Convert text to speech and return audio stream."""
    if MODEL is None:
        raise HTTPException(status_code=500, detail="Model not initialized")

    # Handle voice selection
    try:
        current_voicepack = VOICEPACK
        if voice and voice != DEFAULT_VOICE:
            current_voicepack = load_voice(voice)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if current_voicepack is None:
        raise HTTPException(status_code=500, detail="Voicepack not initialized")

    try:
        log.info(
            f"Generating audio for text: {text[:50]}... (speed: {speed}x, voice: {voice or DEFAULT_VOICE})"
        )
        audio, phonemes = generate(
            MODEL, text, current_voicepack, lang="a", speed=speed
        )
        log.info(f"Generated phonemes: {phonemes}")

        # Strip silence from audio
        audio = strip_silence(audio)

        # Convert to WAV format
        buffer = io.BytesIO()
        wavfile.write(buffer, 24000, audio)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="audio/wav",
            headers={"Content-Disposition": 'attachment; filename="speech.wav"'},
        )

    except Exception as e:
        log.error(f"Failed to generate speech: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@click.command()
@click.option("--port", default=8000, help="Port to run the server on")
@click.option("--host", default="0.0.0.0", help="Host to run the server on")
@click.option("--voice", help="Default voice to use")
@click.option("--list-voices", is_flag=True, help="List available voices and exit")
def main(port: int, host: str, voice: str | None, list_voices: bool):
    """Run the TTS server."""
    if list_voices:
        available_voices = _list_voices()
        print("Available voices:")
        for v in available_voices:
            print(f"  - {v}")
        return

    global DEFAULT_VOICE
    DEFAULT_VOICE = voice

    log.info(f"Starting TTS server on {host}:{port} (device: {DEVICE})")
    if voice:
        log.info(f"Using default voice: {voice}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
