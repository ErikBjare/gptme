"""Tests for the Server-Sent Events (SSE) stream functionality in the V2 API."""

import json
import queue
import threading
import time
from datetime import datetime
from typing import Any

import pytest
import requests

# Skip if flask not installed
pytest.importorskip(
    "flask", reason="flask not installed, install server extras (-E server)"
)

# Import after skip check
from flask.testing import FlaskClient  # noqa
from gptme.init import init  # noqa
from gptme.server.api import create_app  # noqa


@pytest.fixture(autouse=True)
def init_():
    init(None, interactive=False, tool_allowlist=None)


@pytest.fixture
def server_thread():
    """Start a server in a thread for testing."""
    app = create_app()

    # Use a queue to communicate between threads
    event_queue: queue.Queue[dict[str, Any]] = queue.Queue()

    # Find a free port
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("localhost", 0))
    free_port = s.getsockname()[1]
    s.close()

    # Configure the app for testing
    app.config["TESTING"] = True
    app.config["SERVER_NAME"] = f"localhost:{free_port}"

    # Start the server in a thread
    def run_server():
        with app.app_context():
            app.run(port=free_port, threaded=True)

    thread = threading.Thread(target=run_server)
    thread.daemon = True
    thread.start()

    # Give the server time to start
    time.sleep(0.5)

    # Include the port in what we yield
    yield (event_queue, free_port)

    # Note: We don't need to stop the thread explicitly since it's a daemon thread


@pytest.mark.timeout(20)
def test_event_stream(server_thread):
    """Test the event stream endpoint."""
    # Unpack the port from the fixture
    event_queue, port = server_thread

    # Create a conversation
    conversation_id = f"test-sse-{int(time.time())}"

    # Create conversation with system message
    resp = requests.put(
        f"http://localhost:{port}/api/v2/conversations/{conversation_id}",
        json={
            "messages": [
                {
                    "role": "system",
                    "content": "You are an AI assistant for testing.",
                    "timestamp": datetime.now().isoformat(),
                }
            ]
        },
    )

    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    # Create a queue to store received events
    events: queue.Queue[dict[str, Any]] = queue.Queue()

    # Start a thread to listen for events
    def listen_for_events():
        resp = requests.get(
            f"http://localhost:{port}/api/v2/conversations/{conversation_id}/events?session_id={session_id}",
            stream=True,
        )

        try:
            for line in resp.iter_lines():
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        event_data = json.loads(line[6:])
                        events.put(event_data)

                        # If we get a message_added event, we're done
                        if event_data.get("type") == "message_added":
                            break
        except Exception as e:
            events.put({"error": str(e)})
        finally:
            resp.close()

    event_thread = threading.Thread(target=listen_for_events)
    event_thread.daemon = True
    event_thread.start()

    # Give the event stream time to connect
    time.sleep(1)

    # Send a message to trigger an event
    requests.post(
        f"http://localhost:{port}/api/v2/conversations/{conversation_id}",
        json={"role": "user", "content": "Test message"},
    )

    # Wait for the message_added event
    timeout = 5
    start_time = time.time()
    received_events = []

    while time.time() - start_time < timeout:
        try:
            event = events.get(timeout=0.5)
            received_events.append(event)

            if event.get("type") == "message_added":
                break
        except queue.Empty:
            continue

    # Verify we received the expected events
    assert len(received_events) >= 2  # At least connected and message_added

    # Check for connected event
    connected_events = [e for e in received_events if e.get("type") == "connected"]
    assert len(connected_events) == 1
    assert connected_events[0]["session_id"] == session_id

    # Check for message_added event
    message_events = [e for e in received_events if e.get("type") == "message_added"]
    assert len(message_events) == 1
    assert message_events[0]["message"]["role"] == "user"
    assert message_events[0]["message"]["content"] == "Test message"


@pytest.mark.timeout(20)
@pytest.mark.slow
def test_event_stream_with_generation(server_thread):
    """Test that the event stream receives generation events."""
    # Unpack the port from the fixture
    event_queue, port = server_thread

    # This test requires an API connection, so we'll mock the generation
    # rather than actually calling an LLM

    # This test makes a real API request
    # It's marked as 'slow' so it can be skipped in regular test runs with -m "not slow"

    # Create a conversation
    conversation_id = f"test-gen-{int(time.time())}"

    # Create conversation with system message
    resp = requests.put(
        f"http://localhost:{port}/api/v2/conversations/{conversation_id}",
        json={
            "messages": [
                {
                    "role": "system",
                    "content": "You are an AI assistant for testing.",
                    "timestamp": datetime.now().isoformat(),
                }
            ]
        },
    )

    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    # Add a user message
    requests.post(
        f"http://localhost:{port}/api/v2/conversations/{conversation_id}",
        json={"role": "user", "content": "Say hello"},
    )

    # Create a queue to store received events
    events: queue.Queue[dict[str, Any]] = queue.Queue()

    # Start a thread to listen for events
    def listen_for_events():
        resp = requests.get(
            f"http://localhost:{port}/api/v2/conversations/{conversation_id}/events?session_id={session_id}",
            stream=True,
        )

        try:
            for line in resp.iter_lines():
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        event_data = json.loads(line[6:])
                        events.put(event_data)

                        # If we get a generation_complete event, we're done
                        if event_data.get("type") == "generation_complete":
                            break
        except Exception as e:
            events.put({"error": str(e)})
        finally:
            resp.close()

    event_thread = threading.Thread(target=listen_for_events)
    event_thread.daemon = True
    event_thread.start()

    # Give the event stream time to connect
    time.sleep(1)

    # Use a real model instead of mocking
    requests.post(
        f"http://localhost:{port}/api/v2/conversations/{conversation_id}/generate",
        json={"session_id": session_id, "model": "openai/gpt-4o-mini"},
    )

    # Wait for events
    timeout = 10
    start_time = time.time()
    received_events = []

    while time.time() - start_time < timeout:
        try:
            event = events.get(timeout=0.5)
            received_events.append(event)

            if event.get("type") == "generation_complete":
                break
        except queue.Empty:
            continue

    # Check for generation events
    progress_events = [
        e for e in received_events if e.get("type") == "generation_progress"
    ]
    assert len(progress_events) > 0

    # Since we're using a real model, don't check for exact content
    tokens = [e["token"] for e in progress_events]
    response_text = "".join(tokens)
    assert len(response_text) > 0

    # Check for generation_complete event
    complete_events = [
        e for e in received_events if e.get("type") == "generation_complete"
    ]
    assert len(complete_events) == 1
    assert len(complete_events[0]["message"]["content"]) > 0
