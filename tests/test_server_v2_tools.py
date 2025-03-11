"""Tests for the tool confirmation flow in the V2 API."""

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
from gptme.tools import ToolUse  # noqa


@pytest.fixture(autouse=True)
def init_():
    init(None, interactive=False, tool_allowlist=None)


@pytest.fixture
def server_thread():
    """Start a server in a thread for testing."""
    app = create_app()

    # Configure the app for testing
    app.config["TESTING"] = True
    app.config["SERVER_NAME"] = "localhost:5001"  # Different port to avoid conflicts

    # Start the server in a thread
    def run_server():
        with app.app_context():
            app.run(port=5001, threaded=True)

    thread = threading.Thread(target=run_server)
    thread.daemon = True
    thread.start()

    # Give the server time to start
    time.sleep(0.5)

    yield

    # Note: We don't need to stop the thread explicitly since it's a daemon thread


@pytest.mark.timeout(20)
def test_tool_confirmation_flow(server_thread):
    """Test the tool confirmation flow."""
    # First, we'll monkey patch the V2 API's _stream function to return a tool use
    import unittest.mock

    def mock_stream(messages, model, tools=None, max_tokens=None):
        """Mock the _stream function to return a shell tool use."""
        yield "I'll help you list the files. Let me run the command:"
        yield "\n\n```shell\nls -la\n```"

    # Create a conversation
    conversation_id = f"test-tools-{int(time.time())}"

    # Create conversation with system message
    resp = requests.put(
        f"http://localhost:5001/api/v2/conversations/{conversation_id}",
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
        f"http://localhost:5001/api/v2/conversations/{conversation_id}",
        json={"role": "user", "content": "List files in the current directory"},
    )

    # Create a queue to store received events
    events: queue.Queue[dict[str, Any]] = queue.Queue()
    tool_id = None

    # Start a thread to listen for events
    def listen_for_events():
        nonlocal tool_id
        resp = requests.get(
            f"http://localhost:5001/api/v2/conversations/{conversation_id}/events?session_id={session_id}",
            stream=True,
        )

        try:
            for line in resp.iter_lines():
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        event_data = json.loads(line[6:])
                        events.put(event_data)

                        # If we get a tool_pending event, capture the tool_id
                        if event_data.get("type") == "tool_pending":
                            tool_id = event_data.get("tool_id")

                        # If we get a tool_output event, we're done
                        if event_data.get("type") == "tool_output":
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

    # Now mock ToolUse.iter_from_content to return a tool use
    def mock_iter_from_content(content):
        """Mock the ToolUse.iter_from_content method to return a tool use."""

        class MockToolUse:
            def __init__(self):
                self.is_runnable = True
                self.tool = "shell"
                self.args = ["ls", "-la"]

            def __str__(self):
                return "```shell\nls -la\n```"

            # Add any other methods or properties needed by the implementation

        yield MockToolUse()

    # Also mock execute_msg to avoid actually executing commands
    def mock_execute_msg(msg, confirm_func):
        """Mock the execute_msg function to return a dummy response."""
        from gptme.message import Message

        yield Message(
            "system", "total 123\ndrwxr-xr-x  test.txt\ndrwxr-xr-x  example.py"
        )

    # Start generation using our mocks
    with (
        unittest.mock.patch("gptme.server.api_v2._stream", mock_stream),
        unittest.mock.patch(
            "gptme.tools.ToolUse.iter_from_content", mock_iter_from_content
        ),
        unittest.mock.patch("gptme.server.api_v2.execute_msg", mock_execute_msg),
    ):
        requests.post(
            f"http://localhost:5001/api/v2/conversations/{conversation_id}/generate",
            json={"session_id": session_id, "model": "mock-model"},
        )

        # Wait until we get a tool_pending event
        timeout = 10
        start_time = time.time()

        while not tool_id and time.time() - start_time < timeout:
            time.sleep(0.1)

        assert tool_id is not None, "Did not receive tool_pending event"

        # Now confirm the tool execution
        response = requests.post(
            f"http://localhost:5001/api/v2/conversations/{conversation_id}/tool/confirm",
            json={"session_id": session_id, "tool_id": tool_id, "action": "confirm"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    # Wait for all the expected events
    timeout = 10
    start_time = time.time()
    received_events = []

    while time.time() - start_time < timeout:
        try:
            event = events.get(timeout=0.5)
            received_events.append(event)

            # If we've received a tool_output event, we can stop
            if any(e.get("type") == "tool_output" for e in received_events):
                break
        except queue.Empty:
            continue

    # Check for the expected event sequence
    event_types = [e.get("type") for e in received_events if "type" in e]

    # We should see: connected, generation_progress, tool_pending, tool_executing, tool_output
    assert "connected" in event_types
    assert "generation_progress" in event_types
    assert "tool_pending" in event_types
    assert "tool_executing" in event_types
    assert "tool_output" in event_types

    # Verify the tool_pending event contains the expected data
    tool_pending_events = [
        e for e in received_events if e.get("type") == "tool_pending"
    ]
    assert len(tool_pending_events) == 1
    assert tool_pending_events[0]["tool"] == "shell"
    assert tool_pending_events[0]["args"] == ["ls", "-la"]

    # Verify the tool_output event contains expected output
    tool_output_events = [e for e in received_events if e.get("type") == "tool_output"]
    assert len(tool_output_events) == 1

    # Look for "total" followed by numbers (don't hardcode a specific number)
    import re

    assert (
        re.search(r"total \d+", tool_output_events[0]["output"]["content"]) is not None
    )
