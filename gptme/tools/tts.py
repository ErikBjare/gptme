import io
import logging
import queue
import re
import threading
import traceback

import numpy as np
import requests
import scipy.io.wavfile as wavfile
import scipy.signal as signal
import sounddevice as sd

# Setup logging
log = logging.getLogger(__name__)

# Global queue for audio playback
audio_queue: queue.Queue[tuple[np.ndarray, int]] = queue.Queue()
playback_thread = None
current_volume = 1.0
current_speed = 1.0


def set_speed(speed):
    """Set the speaking speed (0.5 to 2.0)."""
    global current_speed
    current_speed = max(0.5, min(2.0, speed))
    log.info(f"TTS speed set to {current_speed:.2f}x")


def set_volume(volume):
    """Set the volume for TTS playback (0.0 to 1.0)."""
    global current_volume
    current_volume = max(0.0, min(1.0, volume))
    log.info(f"TTS volume set to {current_volume:.2f}")


def stop():
    """Stop audio playback and clear the queue."""
    sd.stop()
    clear_queue()
    log.info("Stopped TTS playback and cleared queue")


def clear_queue():
    """Clear the audio queue without stopping current playback."""
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
            audio_queue.task_done()
        except queue.Empty:
            break


def split_text(text, max_words=50):
    """Split text into chunks at sentence boundaries, respecting word count."""
    # First split into sentences
    sentences = re.split(r"([.!?]+[\s\n]*)", text)
    sentences = [
        "".join(t)
        for t in zip(
            sentences[::2],
            sentences[1::2] + [""] * (len(sentences[::2]) - len(sentences[1::2])),
        )
    ]
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks = []
    current_chunk: list[str] = []
    current_word_count = 0

    for sentence in sentences:
        # Count words in sentence
        words_in_sentence = len(sentence.split())

        # If adding this sentence would exceed max_words
        if current_word_count + words_in_sentence > max_words and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_word_count = 0

        current_chunk.append(sentence)
        current_word_count += words_in_sentence

    # Add any remaining text
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def audio_player_thread():
    """Background thread for playing audio."""
    while True:
        try:
            # Get audio data from queue
            data, sample_rate = audio_queue.get()
            if data is None:  # Sentinel value to stop thread
                break

            # Apply volume
            data = data * current_volume

            # Play audio
            log.debug("Playing audio...")
            sd.play(data, sample_rate)
            sd.wait()  # Wait until audio is finished playing
            log.debug("Done playing audio")

            audio_queue.task_done()
        except Exception as e:
            log.error(f"Error in audio playback: {e}")


def ensure_playback_thread():
    """Ensure the playback thread is running."""
    global playback_thread
    if playback_thread is None or not playback_thread.is_alive():
        playback_thread = threading.Thread(target=audio_player_thread, daemon=True)
        playback_thread.start()


def resample_audio(data, orig_sr, target_sr):
    """Resample audio data to target sample rate."""
    if orig_sr == target_sr:
        return data

    duration = len(data) / orig_sr
    num_samples = int(duration * target_sr)
    return signal.resample(data, num_samples)


def speak(
    text, device_name="Fosi Audio BT20A", block=False, verbose=False, interrupt=True
):
    """Speak text using Kokoro TTS server.

    The TTS system supports:
    - Speed control via set_speed(0.5 to 2.0)
    - Volume control via set_volume(0.0 to 1.0)
    - Automatic chunking of long texts
    - Non-blocking operation with optional blocking mode
    - Interruption of current speech

    Args:
        text: Text to speak
        device_name: Name of audio output device to use
        block: If True, wait for audio to finish playing
        verbose: If True, print detailed progress information
        interrupt: If True, stop current speech and clear queue before speaking

    Example:
        >>> from gptme.tools.tts import speak, set_speed, set_volume
        >>> set_volume(0.8)  # Set comfortable volume
        >>> set_speed(1.2)   # Slightly faster speech
        >>> speak("Hello, world!")  # Non-blocking by default
        >>> speak("Important message!", interrupt=True)  # Interrupts previous speech
    """
    if verbose:
        print(f"Speaking text ({len(text)} chars)...")
    else:
        log.info(f"Speaking text ({len(text)} chars)")

    # Stop current speech if requested
    if interrupt:
        clear_queue()

    # Split text into chunks if needed
    chunks = split_text(text)
    if len(chunks) > 1 and verbose:
        print(f"Split into {len(chunks)} chunks")

    try:
        # Find the device (do this once)
        devices = sd.query_devices()
        device_id = None
        for i, dev in enumerate(devices):
            if device_name in str(dev["name"]):
                device_id = i
                device_info = dev
                break

        if device_id is None:
            log.warning(f"Device '{device_name}' not found, using default")
            device_info = sd.query_devices(kind="output")
        else:
            sd.default.device = device_id

        # Get device's default sample rate
        device_sr = int(device_info["default_samplerate"])

        # Ensure playback thread is running
        ensure_playback_thread()

        # Process each chunk
        for chunk in chunks:
            # Make request to the TTS server
            url = "http://localhost:8000/tts"
            params = {"text": chunk, "speed": current_speed}

            response = requests.get(url, params=params)

            if response.status_code != 200:
                log.error(f"TTS server returned status {response.status_code}")
                if response.content:
                    log.error(f"Error content: {response.content.decode()}")
                continue

            # Convert response to audio
            audio_data = io.BytesIO(response.content)
            sample_rate, data = wavfile.read(audio_data)

            if verbose:
                print(
                    f"Audio: {len(data)} samples at {sample_rate}Hz ({len(data)/sample_rate:.2f} seconds)"
                )

            # Resample if needed
            if sample_rate != device_sr:
                data = resample_audio(data, sample_rate, device_sr)
                sample_rate = device_sr

            # Normalize audio to float32 in range [-1, 1]
            if data.dtype != np.float32:
                data = data.astype(np.float32) / np.iinfo(data.dtype).max

            # Queue audio for playback
            audio_queue.put((data, sample_rate))

        if block:
            audio_queue.join()  # Wait for audio to finish playing

    except Exception as e:
        log.error(f"Failed to speak text: {e}")
        if verbose:
            traceback.print_exc()
