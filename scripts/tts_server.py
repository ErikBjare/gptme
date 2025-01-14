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

import io
import logging
import subprocess
import sys
from pathlib import Path

import scipy.io.wavfile as wavfile
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from kokoro import generate
from models import build_model

# Add Kokoro-82M to Python path
kokoro_path = Path("Kokoro-82M").absolute()
sys.path.insert(0, str(kokoro_path))


# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="TTS Server")

# Global variables for model and voicepack
MODEL = None
VOICEPACK = None
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def init_model():
    """Initialize the Kokoro TTS model and voicepack."""
    global MODEL, VOICEPACK

    try:
        # Install espeak-ng if not already installed
        try:
            subprocess.run(["espeak-ng", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            log.info("Installing espeak-ng...")
            subprocess.run(
                ["sudo", "apt-get", "install", "-y", "espeak-ng"], check=True
            )

        # Import and initialize

        log.info("Loading model...")
        MODEL = build_model(str(kokoro_path / "kokoro-v0_19.pth"), DEVICE)

        log.info("Loading voicepack...")
        VOICEPACK = torch.load(kokoro_path / "voices/af.pt", weights_only=True).to(
            DEVICE
        )
        log.info("Model initialization complete")

    except Exception as e:
        log.error(f"Failed to initialize model: {e}")
        raise


@app.on_event("startup")
async def startup_event():
    """Initialize model on startup."""
    init_model()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model_loaded": MODEL is not None,
        "voicepack_loaded": VOICEPACK is not None,
    }


@app.get("/tts")
async def text_to_speech(text: str, speed: float = 1.0):
    """Convert text to speech and return audio stream."""
    if MODEL is None:
        raise HTTPException(status_code=500, detail="Model not initialized")
    if VOICEPACK is None:
        raise HTTPException(status_code=500, detail="Voicepack not initialized")

    try:
        log.info(f"Generating audio for text: {text[:50]}... (speed: {speed}x)")
        audio, phonemes = generate(MODEL, text, VOICEPACK, lang="a", speed=speed)
        log.info(f"Generated phonemes: {phonemes}")

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


if __name__ == "__main__":
    log.info(f"Starting TTS server on port 8000 (device: {DEVICE})")
    uvicorn.run(app, host="0.0.0.0", port=8000)
