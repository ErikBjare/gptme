#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pip",
#   "fastapi>=0.109.0",
#   "uvicorn>=0.27.0",
#   "kokoro>=0.3.4",
#   "scipy>=1.11.0",
#   "soundfile>=0.12.1",
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
import shutil
from textwrap import shorten

import click
import kokoro
import numpy as np
import scipy.io.wavfile as wavfile
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from kokoro import KPipeline

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="TTS Server")

# Global variables
DEFAULT_VOICE = "af_heart"  # Default voice
DEFAULT_LANG = "a"  # Default language (American English)
pipeline = None

# Language codes and their descriptions
LANGUAGE_CODES = {
    "a": "American English",
    "b": "British English",
    "j": "Japanese",
    "z": "Mandarin Chinese",
    "e": "Spanish",
    "f": "French",
    "h": "Hindi",
    "i": "Italian",
    "p": "Brazilian Portuguese",
}


def _list_voices():
    """
    List all available voices for the current language.

    Source: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
    """
    # American English voices (most complete set)
    if DEFAULT_LANG == "a":
        return [
            "af_heart",
            "af_alloy",
            "af_aoede",
            "af_bella",
            "af_jessica",
            "af_kore",
            "af_nicole",
            "af_nova",
            "af_river",
            "af_sarah",
            "af_sky",
            "am_adam",
            "am_echo",
            "am_eric",
            "am_fenrir",
            "am_liam",
            "am_michael",
            "am_onyx",
            "am_puck",
            "am_santa",
        ]
    # British English voices
    elif DEFAULT_LANG == "b":
        return [
            "bf_alice",
            "bf_emma",
            "bf_isabella",
            "bf_lily",
            "bm_daniel",
            "bm_fable",
            "bm_george",
            "bm_lewis",
        ]
    # Japanese voices
    elif DEFAULT_LANG == "j":
        return ["jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo"]
    # Mandarin Chinese voices
    elif DEFAULT_LANG == "z":
        return [
            "zf_xiaobei",
            "zf_xiaoni",
            "zf_xiaoxiao",
            "zf_xiaoyi",
            "zm_yunjian",
            "zm_yunxi",
            "zm_yunxia",
            "zm_yunyang",
        ]
    # Spanish voices
    elif DEFAULT_LANG == "e":
        return ["ef_dora", "em_alex", "em_santa"]
    # French voices
    elif DEFAULT_LANG == "f":
        return ["ff_siwis"]
    # Hindi voices
    elif DEFAULT_LANG == "h":
        return ["hf_alpha", "hf_beta", "hm_omega", "hm_psi"]
    # Italian voices
    elif DEFAULT_LANG == "i":
        return ["if_sara", "im_nicola"]
    # Brazilian Portuguese voices
    elif DEFAULT_LANG == "p":
        return ["pf_dora", "pm_alex", "pm_santa"]

    return ["af_heart"]  # Default fallback to best quality voice


def _check_espeak():
    """Check if espeak/espeak-ng is installed."""
    if not any([shutil.which("espeak"), shutil.which("espeak-ng")]):
        raise RuntimeError(
            "Failed to find `espeak` or `espeak-ng`. Try to install it using 'sudo apt-get install espeak-ng' or equivalent"
        ) from None


def init_model(voice: str | None = None):
    """Initialize the Kokoro TTS pipeline."""
    global pipeline, DEFAULT_VOICE

    try:
        _check_espeak()

        # Use specified voice or default
        voice_name = voice or DEFAULT_VOICE

        # Initialize the pipeline with default language
        pipeline = KPipeline(lang_code=DEFAULT_LANG)

        # Verify voice exists (this is a placeholder check)
        available_voices = _list_voices()
        if voice_name not in available_voices:
            raise ValueError(
                f"Voice {voice_name} not found. Available voices: {available_voices}"
            )

        DEFAULT_VOICE = voice_name
        log.info(f"Pipeline initialization complete (using voice: {voice_name})")

    except Exception as e:
        log.error(f"Failed to initialize pipeline: {e}")
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


@app.get("/")
async def root():
    return {"message": "Hello World, I am a TTS server based on Kokoro TTS"}


@app.get("/health")
async def health():
    """Health check endpoint.

    Returns information about:
    - Server status
    - Default and available voices
    - Supported languages
    - Version information
    """
    return {
        "status": "healthy",
        "voice": {
            "default": DEFAULT_VOICE,
            "available": _list_voices(),
        },
        "language": {
            "default": DEFAULT_LANG,
            "name": LANGUAGE_CODES[DEFAULT_LANG],
            "supported": LANGUAGE_CODES,
        },
        "version": {
            "kokoro": kokoro.__version__,
        },
    }


@app.get("/tts")
async def text_to_speech(text: str, speed: float = 1.0, voice: str | None = None):
    """Convert text to speech and return audio stream."""
    assert pipeline
    # Handle voice selection
    try:
        current_voice = voice or DEFAULT_VOICE
        if current_voice not in _list_voices():
            raise ValueError(f"Voice {current_voice} not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        log.info(
            f"Generating audio for text: {shorten(text, 50, placeholder='...')} (speed: {speed}x, voice: {current_voice})"
        )

        # Generate audio using KPipeline
        # Note: KPipeline returns a generator of (graphemes, phonemes, audio) tuples
        # We'll concatenate all audio segments
        audio_segments = []
        for _, _, audio in pipeline(text, voice=current_voice, speed=speed):
            audio_segments.append(audio)

        # Concatenate all audio segments
        if audio_segments:
            audio = np.concatenate(audio_segments)

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
        else:
            raise ValueError("No audio generated")

    except Exception as e:
        log.error(f"Failed to generate speech: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@click.command()
@click.option("--port", default=8000, help="Port to run the server on")
@click.option("--host", default="0.0.0.0", help="Host to run the server on")
@click.option("--voice", help="Default voice to use")
@click.option(
    "--lang",
    default="a",
    help="Language code (a=American English, b=British English, etc)",
)
@click.option("--list-voices", is_flag=True, help="List available voices and exit")
def main(port: int, host: str, voice: str | None, lang: str, list_voices: bool):
    """Run the TTS server."""
    global pipeline, DEFAULT_VOICE, DEFAULT_LANG
    if list_voices:
        # Initialize pipeline with specified language
        DEFAULT_LANG = lang
        pipeline = KPipeline(lang_code=lang)
        available_voices = _list_voices()
        print("Available voices:")
        for v in available_voices:
            print(f"  - {v}")
        return

    if voice:
        DEFAULT_VOICE = voice
    DEFAULT_LANG = lang

    log.info(f"Starting TTS server on {host}:{port}")
    log.info(f"Using language: {DEFAULT_LANG}")
    if voice:
        log.info(f"Using default voice: {voice}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
