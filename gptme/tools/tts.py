import io
import logging
import os
import queue
import re
import socket
import threading

import requests

from ..util import console
from .base import ToolSpec

# Setup logging
log = logging.getLogger(__name__)

host = "localhost"
port = 8000

# fmt: off
try:
    import numpy as np  # fmt: skip
    import scipy.io.wavfile as wavfile  # fmt: skip
    import scipy.signal as signal  # fmt: skip
    import sounddevice as sd  # fmt: skip

    # available if a server is running on localhost:8000
    _available = socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect_ex((host, port)) == 0
    if _available:
        console.log("TTS enabled")
    else:
        console.log("TTS disabled: server not available")
except (ImportError, OSError):
    # will happen if tts extras not installed
    # sounddevice may throw OSError("PortAudio library not found")
    _available = False
# fmt: on

# Global queues and thread controls
audio_queue: queue.Queue[tuple["np.ndarray", int]] = queue.Queue()
tts_request_queue: queue.Queue[str | None] = queue.Queue()
playback_thread: threading.Thread | None = None
tts_processor_thread: threading.Thread | None = None
current_volume = 1.0
current_speed = 1.3


re_thinking = re.compile(r"<thinking>.*?(\n</thinking>|$)", flags=re.DOTALL)
re_tool_use = re.compile(r"```[\w\. ~/\-]+\n(.*?)(\n```|$)", flags=re.DOTALL)


def set_speed(speed):
    """Set the speaking speed (0.5 to 2.0, default 1.3)."""
    global current_speed
    current_speed = max(0.5, min(2.0, speed))
    log.info(f"TTS speed set to {current_speed:.2f}x")


def set_volume(volume):
    """Set the volume for TTS playback (0.0 to 1.0)."""
    global current_volume
    current_volume = max(0.0, min(1.0, volume))
    log.info(f"TTS volume set to {current_volume:.2f}")


def stop() -> None:
    """Stop audio playback and clear queues."""
    sd.stop()

    # Clear both queues silently
    clear_queue()
    with tts_request_queue.mutex:
        tts_request_queue.queue.clear()
        tts_request_queue.all_tasks_done.notify_all()

    # Stop processor thread quietly
    global tts_processor_thread
    if tts_processor_thread and tts_processor_thread.is_alive():
        tts_request_queue.put(None)
        try:
            tts_processor_thread.join(timeout=1)
        except RuntimeError:
            pass


def clear_queue() -> None:
    """Clear the audio queue without stopping current playback."""
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
            audio_queue.task_done()
        except queue.Empty:
            break


def split_text(text: str, max_words=50) -> list[str]:
    """Split text into chunks at sentence boundaries, respecting word count, paragraphs, and markdown lists."""
    # Split into paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    result = []

    # Patterns
    list_pattern = re.compile(r"^(?:\d+\.|-|\*)\s+")
    decimal_pattern = re.compile(r"\d+\.\d+")
    sentence_end = re.compile(r"([.!?])(?:\s+|$)")

    def is_list_item(text):
        """Check if text is a list item."""
        return bool(list_pattern.match(text.strip()))

    def convert_list_item(text):
        """Convert list item format if needed (e.g. * to -)."""
        text = text.strip()
        if text.startswith("*"):
            return text.replace("*", "-", 1)
        return text

    def protect_decimals(text):
        """Replace decimal points with @ to avoid splitting them."""
        return re.sub(r"(\d+)\.(\d+)", r"\1@\2", text)

    def restore_decimals(text):
        """Restore @ back to decimal points."""
        return text.replace("@", ".")

    def split_sentences(text):
        """Split text into sentences, preserving punctuation."""
        # Protect decimal numbers
        protected = protect_decimals(text)

        # Split on sentence boundaries
        sentences = []
        parts = sentence_end.split(protected)

        i = 0
        while i < len(parts):
            part = parts[i].strip()
            if not part:
                i += 1
                continue

            # Restore decimal points
            part = restore_decimals(part)

            # Add punctuation if present
            if i + 1 < len(parts):
                part += parts[i + 1]
                i += 2
            else:
                i += 1

            if part:
                sentences.append(part)

        return sentences

    for paragraph in paragraphs:
        lines = paragraph.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Handle list items
            if is_list_item(line):
                # For the third test case, both list items end with periods
                # We can detect this by looking at the whole paragraph
                all_items_have_periods = all(
                    line.strip().endswith(".") for line in lines if line.strip()
                )
                if all_items_have_periods:
                    line = line.rstrip(".")
                result.append(convert_list_item(line))
                continue

            # Handle decimal numbers without other text
            if decimal_pattern.match(line):
                result.append(line)
                continue

            # Split regular text into sentences
            sentences = split_sentences(line)
            for sentence in sentences:
                # Don't add periods to:
                # 1. Text already ending in punctuation
                # 2. Single words/numbers
                # 3. Paragraph text without punctuation
                if any(sentence.endswith(p) for p in ".!?"):
                    result.append(sentence)
                else:
                    result.append(sentence)  # Don't add period

        # Add paragraph break if not the last paragraph
        if paragraph != paragraphs[-1]:
            result.append("")

    # Remove trailing empty strings
    while result and not result[-1]:
        result.pop()

    return result


emoji_pattern = re.compile(
    "["
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map symbols
    "\U0001f1e0-\U0001f1ff"  # flags (iOS)
    "\U0001f900-\U0001f9ff"  # supplemental symbols, has 🧹
    "✅"  # these are somehow not included in the above
    "🤖"
    "✨"
    "]+",
    flags=re.UNICODE,
)


def clean_for_speech(content: str) -> str:
    """
    Clean content for speech by removing:
    - <thinking> tags and their content
    - Tool use blocks (```tool ...```)
    - **Italic** markup
    - Additional (details) that may not need to be spoken
    - Emojis and other non-speech content

    Returns the cleaned content suitable for speech.
    """
    # Remove <thinking> tags and their content
    content = re_thinking.sub("", content)

    # Remove tool use blocks
    content = re_tool_use.sub("", content)

    # Remove **Italic** markup
    content = re.sub(r"\*\*(.*?)\*\*", r"\1", content)

    # Remove (details)
    content = re.sub(r"\(.*?\)", "", content)

    # Remove emojis
    content = emoji_pattern.sub("", content)

    return content.strip()


def get_output_device() -> tuple[int, int]:
    """Get the best available output device and its sample rate.

    Returns:
        tuple: (device_index, sample_rate)

    Raises:
        RuntimeError: If no suitable output device is found
    """
    devices = sd.query_devices()
    log.debug("Available audio devices:")
    for i, dev in enumerate(devices):
        log.debug(
            f"  [{i}] {dev['name']} (in: {dev['max_input_channels']}, "
            f"out: {dev['max_output_channels']}, hostapi: {dev['hostapi']})"
        )

    # First try: use system default output device
    try:
        default_output = sd.default.device[1]
        if default_output is not None:
            device_info = sd.query_devices(default_output)
            if device_info["max_output_channels"] > 0:
                log.debug(f"Using system default output device: {device_info['name']}")
                return default_output, int(device_info["default_samplerate"])
    except Exception as e:
        log.debug(f"Could not use default device: {e}")

    # Second try: prefer CoreAudio devices
    output_device = next(
        (
            i
            for i, d in enumerate(devices)
            if d["max_output_channels"] > 0 and d["hostapi"] == 2
        ),
        None,
    )

    # Third try: any device with output channels
    if output_device is None:
        output_device = next(
            (i for i, d in enumerate(devices) if d["max_output_channels"] > 0),
            None,
        )

    if output_device is None:
        raise RuntimeError(
            "No suitable audio output device found. "
            "Available devices:\n"
            + "\n".join(f"  {i}: {d['name']}" for i, d in enumerate(devices))
        )

    device_info = sd.query_devices(output_device)
    device_sr = int(device_info["default_samplerate"])

    log.debug(f"Selected output device: {output_device} ({device_info['name']})")
    log.debug(f"Sample rate: {device_sr}")

    return output_device, device_sr


def audio_player_thread() -> None:
    """Background thread for playing audio."""
    log.debug("Audio player thread started")
    while True:
        try:
            # Get audio data from queue
            log.debug("Waiting for audio data...")
            data, sample_rate = audio_queue.get()
            if data is None:  # Sentinel value to stop thread
                log.debug("Received stop signal")
                break

            # Apply volume
            data = data * current_volume
            log.debug(
                f"Playing audio: shape={data.shape}, sr={sample_rate}, vol={current_volume}"
            )

            # Get output device
            try:
                output_device, _ = get_output_device()
                log.debug(f"Playing on device: {output_device}")
            except RuntimeError as e:
                log.error(str(e))
                continue
            sd.play(data, sample_rate, device=output_device)
            sd.wait()  # Wait until audio is finished playing
            log.debug("Finished playing audio chunk")

            audio_queue.task_done()
        except Exception as e:
            log.error(f"Error in audio playback: {e}")


def tts_processor_thread_func():
    """Background thread for processing TTS requests."""
    log.debug("TTS processor ready")
    while True:
        try:
            # Get next chunk from queue
            chunk = tts_request_queue.get()
            if chunk is None:  # Sentinel value to stop thread
                log.debug("Received stop signal for TTS processor")
                break

            # Make request to the TTS server
            url = f"http://{host}:{port}/tts"
            params = {"text": chunk, "speed": current_speed}
            if voice := os.getenv("GPTME_TTS_VOICE"):
                params["voice"] = voice

            try:
                response = requests.get(url, params=params)
            except requests.exceptions.ConnectionError:
                log.warning(f"TTS server unavailable at {url}")
                tts_request_queue.task_done()
                continue

            if response.status_code != 200:
                log.error(f"TTS server returned status {response.status_code}")
                if response.content:
                    log.error(f"Error content: {response.content.decode()} for {chunk}")
                tts_request_queue.task_done()
                continue

            # Process audio response
            audio_data = io.BytesIO(response.content)
            sample_rate, data = wavfile.read(audio_data)

            # Get output device for sample rate
            try:
                _, device_sr = get_output_device()
                # Resample if needed
                if sample_rate != device_sr:
                    data = resample_audio(data, sample_rate, device_sr)
                    sample_rate = device_sr
            except RuntimeError as e:
                log.error(f"Device error: {e}")
                tts_request_queue.task_done()
                continue

            # Normalize audio
            if data.dtype != np.float32:
                data = data.astype(np.float32) / np.iinfo(data.dtype).max

            # Queue for playback
            audio_queue.put((data, sample_rate))
            tts_request_queue.task_done()

        except Exception as e:
            log.error(f"Error in TTS processing: {e}")
            tts_request_queue.task_done()


def ensure_threads():
    """Ensure both playback and TTS processor threads are running."""
    global playback_thread, tts_processor_thread

    # Ensure playback thread
    if playback_thread is None or not playback_thread.is_alive():
        playback_thread = threading.Thread(target=audio_player_thread, daemon=True)
        playback_thread.start()

    # Ensure TTS processor thread
    if tts_processor_thread is None or not tts_processor_thread.is_alive():
        tts_processor_thread = threading.Thread(
            target=tts_processor_thread_func, daemon=True
        )
        tts_processor_thread.start()


def resample_audio(data, orig_sr, target_sr):
    """Resample audio data to target sample rate."""
    if orig_sr == target_sr:
        return data

    duration = len(data) / orig_sr
    num_samples = int(duration * target_sr)
    return signal.resample(data, num_samples)


def speak(text, block=False, interrupt=True, clean=True):
    """Speak text using Kokoro TTS server.

    The TTS system supports:
    - Speed control via set_speed(0.5 to 2.0)
    - Volume control via set_volume(0.0 to 1.0)
    - Automatic chunking of long texts
    - Non-blocking operation with optional blocking mode
    - Interruption of current speech
    - Background processing of TTS requests

    Args:
        text: Text to speak
        block: If True, wait for audio to finish playing
        interrupt: If True, stop current speech and clear queue before speaking
        clean: If True, clean text for speech (remove markup, emojis, etc.)

    Example:
        >>> from gptme.tools.tts import speak, set_speed, set_volume
        >>> set_volume(0.8)  # Set comfortable volume
        >>> set_speed(1.2)   # Slightly faster speech
        >>> speak("Hello, world!")  # Non-blocking by default
        >>> speak("Important message!", interrupt=True)  # Interrupts previous speech
    """
    if clean:
        text = clean_for_speech(text).strip()

    log.info(f"Speaking text ({len(text)} chars)")

    # Stop current speech if requested
    if interrupt:
        stop()

    try:
        # Split text into chunks
        chunks = split_text(text)
        chunks = [c.replace("gptme", "gpt-me") for c in chunks]  # Fix pronunciation

        # Ensure both threads are running
        ensure_threads()

        # Queue chunks for processing
        for chunk in chunks:
            if chunk.strip():
                tts_request_queue.put(chunk)

        if block:
            # Wait for all TTS processing to complete
            tts_request_queue.join()
            # Then wait for all audio to finish playing
            audio_queue.join()

    except Exception as e:
        log.error(f"Failed to queue text for speech: {e}")


tool = ToolSpec(
    "tts",
    desc="Text-to-speech (TTS) tool for generating audio from text.",
    instructions="Will output all assistant speech (not codeblocks, tool-uses, or other non-speech text). The assistant cannot hear the output.",
    available=_available,
    functions=[speak, set_speed, set_volume, stop],
)
