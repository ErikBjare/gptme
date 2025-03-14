"""Tests for the tool confirmation flow in the V2 API."""

import json
import logging
import queue
import re
import socket
import threading
import time
import unittest.mock
import uuid
from collections.abc import Generator
from datetime import datetime
from typing import Any

import pytest
import requests
from gptme.init import init  # noqa
from gptme.logmanager import LogManager
from gptme.message import Message
from gptme.server.api import create_app  # noqa
from gptme.server.api_v2 import SessionManager

logger = logging.getLogger(__name__)

# Skip if flask not installed
pytest.importorskip(
    "flask", reason="flask not installed, install server extras (-E server)"
)

# Import after skip check


@pytest.fixture(autouse=True)
def init_():
    init(None, interactive=False, tool_allowlist=None)


@pytest.fixture
def server_thread():
    """Start a server in a thread for testing."""
    app = create_app()

    # Find a free port

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("localhost", 0))  # Let OS assign a free port
    port = s.getsockname()[1]
    s.close()

    # Configure the app for testing
    app.config["TESTING"] = True
    app.config["SERVER_NAME"] = f"localhost:{port}"

    # Start the server in a thread
    def run_server():
        with app.app_context():
            app.run(port=port, threaded=True)

    thread = threading.Thread(target=run_server)
    thread.daemon = True
    thread.start()

    # Give the server time to start
    time.sleep(0.5)

    yield port  # Return the port to the test

    # Note: We don't need to stop the thread explicitly since it's a daemon thread


@pytest.mark.timeout(20)
def test_tool_confirmation_flow(server_thread):
    """Test the tool confirmation flow."""
    # Get the port from the server_thread fixture
    port = server_thread

    # First, we'll monkey patch the V2 API's _stream function to return a tool use
    def mock_stream(
        messages, model, tools=None, max_tokens=None
    ) -> Generator[str, None, None]:
        """Mock the _stream function to return a shell tool use."""
        yield "I'll help you list the files. Let me run the command:"
        yield "\n\n```shell\nls -la\n```"

    # Create a conversation
    conversation_id = f"test-tools-{int(time.time())}"

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
        json={"role": "user", "content": "List files in the current directory"},
    )

    # Create a queue to store received events
    events: queue.Queue[dict[str, Any]] = queue.Queue()
    tool_id = None

    # Start a thread to listen for events
    def listen_for_events():
        nonlocal tool_id
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

            def execute(self, *args, **kwargs):
                """Mock the execute method to return a dummy response."""
                yield Message(
                    "system", "total 123\ndrwxr-xr-x  test.txt\ndrwxr-xr-x  example.py"
                )

            # Add any other methods or properties needed by the implementation

        yield MockToolUse()

    # Also mock execute_msg to avoid actually executing commands
    # FIXME: duplicate of MockToolUse.execute above
    def mock_execute_msg(msg, confirm_func):
        """Mock the execute_msg function to return a dummy response."""

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
            f"http://localhost:{port}/api/v2/conversations/{conversation_id}/generate",
            json={
                "session_id": session_id,
                "model": "openai/mock-model",
            },  # Add provider prefix
        )

        # Wait until we get a tool_pending event
        timeout = 10
        start_time = time.time()

        while not tool_id and time.time() - start_time < timeout:
            time.sleep(0.1)

        assert tool_id is not None, "Did not receive tool_pending event"

        # Now confirm the tool execution
        response = requests.post(
            f"http://localhost:{port}/api/v2/conversations/{conversation_id}/tool/confirm",
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
    assert re.search(r"total \d+", tool_output_events[0]["content"]) is not None

    # Verify that the messages were actually persisted in the conversation
    time.sleep(0.5)  # Give a moment for any async operations to complete

    # Get the conversation from the API
    resp = requests.get(
        f"http://localhost:{port}/api/v2/conversations/{conversation_id}"
    )
    assert resp.status_code == 200

    conversation_data = resp.json()
    messages = conversation_data["log"]

    # Should now have 4 messages:
    # 1. System message
    # 2. User message asking to list files
    # 3. Assistant message with the tool use
    # 4. System message with the tool output
    assert len(messages) == 4, f"Expected 4 messages, got {len(messages)}: {messages}"

    # Check that our tool output was persisted
    assert messages[3]["role"] == "system"
    assert re.search(r"total \d+", messages[3]["content"]) is not None


@pytest.mark.timeout(20)
def test_tool_edit_flow(server_thread):
    """Test editing a tool before execution."""
    # Get port from fixture
    port = server_thread

    # Create our mocks similar to the previous test
    def mock_stream(
        messages, model, tools=None, max_tokens=None
    ) -> Generator[str, None, None]:
        yield "I'll create a simple Python script. Let me use Python:"
        yield "\n\n```python\nprint('Hello, world!')\n```"

    conversation_id = f"test-tool-edit-{int(time.time())}"

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
        json={"role": "user", "content": "Write a simple Python hello world script"},
    )

    # Set up event listening
    events: queue.Queue[dict[str, Any]] = queue.Queue()
    tool_id = None

    def listen_for_events():
        nonlocal tool_id
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
                        if event_data.get("type") == "tool_pending":
                            tool_id = event_data.get("tool_id")
        except Exception as e:
            events.put({"error": str(e)})
        finally:
            resp.close()

    event_thread = threading.Thread(target=listen_for_events)
    event_thread.daemon = True
    event_thread.start()
    time.sleep(1)  # Give time to connect

    # Mock tool detection and execution
    def mock_iter_from_content(content):
        class MockToolUse:
            def __init__(self):
                self.is_runnable = True
                self.tool = "ipython"
                self.args = []
                self.content = "print('Hello, world!')"

            def __str__(self):
                return "```python\nprint('Hello, world!')\n```"

            def execute(self, *args, **kwargs):
                yield Message("system", "Hello, world!")

        yield MockToolUse()

    # Mock tool execution with edited content
    def mock_execute_msg(msg, confirm_func):
        # Check if this is the edited version
        if "Edited" in msg.content or "edited" in msg.content:
            yield Message("system", "Hello, edited world!")
        else:
            yield Message("system", "Hello, world!")

    # We need to be creative with how we mock the await_tool_execution function
    # to ensure the tool_output event is actually sent
    def mock_await_tool_execution(
        conversation_id, session, tool_id, tooluse, edited_content=None
    ):
        # Get original function to call it directly with the right arguments

        # First, we'll send the tool_executing event
        from gptme.server.api_v2 import ToolExecutingEvent, ToolOutputEvent

        SessionManager.add_event(
            conversation_id, ToolExecutingEvent(tool_id=tool_id, type="tool_executing")
        )

        # Let's manually create and send a tool output event
        output_event = ToolOutputEvent(
            tool_id=tool_id,
            role="system",
            content="Hello, edited world!" if edited_content else "Hello, world!",
            timestamp=datetime.now().isoformat(),
            type="tool_output",
        )
        SessionManager.add_event(conversation_id, output_event)

        # Mark the tool as completed
        if tool_id in session.pending_tools:
            del session.pending_tools[tool_id]

        # Don't call resume_generation - we're just testing tool output

    # Start generation with mocks
    with (
        unittest.mock.patch("gptme.server.api_v2._stream", mock_stream),
        unittest.mock.patch(
            "gptme.tools.ToolUse.iter_from_content", mock_iter_from_content
        ),
        unittest.mock.patch("gptme.server.api_v2.execute_msg", mock_execute_msg),
        unittest.mock.patch(
            "gptme.server.api_v2.await_tool_execution", mock_await_tool_execution
        ),
        # Also mock resume_generation to avoid Claude API errors
        unittest.mock.patch(
            "gptme.server.api_v2.resume_generation", lambda *args, **kwargs: None
        ),
    ):
        requests.post(
            f"http://localhost:{port}/api/v2/conversations/{conversation_id}/generate",
            json={"session_id": session_id, "model": "openai/mock-model"},
        )

        # Wait for tool_pending event
        timeout = 10
        start_time = time.time()
        while not tool_id and time.time() - start_time < timeout:
            time.sleep(0.1)

        assert tool_id is not None, "Did not receive tool_pending event"

        # Edit the tool with modified code
        edited_content = "```python\nprint('Hello, edited world!')\n```"
        response = requests.post(
            f"http://localhost:{port}/api/v2/conversations/{conversation_id}/tool/confirm",
            json={
                "session_id": session_id,
                "tool_id": tool_id,
                "action": "edit",
                "content": edited_content,
            },
        )
        assert response.status_code == 200

    # Wait for events to complete
    timeout = 10
    start_time = time.time()
    received_events = []

    while time.time() - start_time < timeout:
        try:
            event = events.get(timeout=0.5)
            received_events.append(event)
            if any(e.get("type") == "tool_output" for e in received_events):
                break
        except queue.Empty:
            continue

    # Verify events sequence includes tool_pending and tool_executing
    # (tool_output might not come because of our mocking approach)
    event_types = [e.get("type") for e in received_events if "type" in e]
    assert "tool_pending" in event_types

    # We expect at least the tool_executing event
    assert "tool_executing" in event_types, f"Expected tool_executing in {event_types}"

    # Verify message persistence - this is the key part we're testing
    time.sleep(0.5)
    resp = requests.get(
        f"http://localhost:{port}/api/v2/conversations/{conversation_id}"
    )
    assert resp.status_code == 200

    conversation_data = resp.json()
    messages = conversation_data["log"]

    # Should have at least the following messages:
    # 1. System message
    # 2. User message
    # 3. Assistant message with tool use (might be truncated)
    # 4. System message about edit or tool output
    assert (
        len(messages) >= 3
    ), f"Expected at least 3 messages, got {len(messages)}: {messages}"

    # Check that assistant message exists with the right role
    assert (
        messages[2]["role"] == "assistant"
    ), f"Expected assistant message, got {messages[2]}"


@pytest.mark.timeout(20)
def test_tool_skip_flow(server_thread):
    """Test skipping a tool execution."""
    # Get port from fixture
    port = server_thread

    # Create mocks
    def mock_stream(
        messages, model, tools=None, max_tokens=None
    ) -> Generator[str, None, None]:
        yield "I'll execute this command:"
        yield "\n\n```shell\nrm -rf /\n```"  # A dangerous command that should be skipped

    conversation_id = f"test-tool-skip-{int(time.time())}"

    # Create conversation
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

    # Add user message
    requests.post(
        f"http://localhost:{port}/api/v2/conversations/{conversation_id}",
        json={"role": "user", "content": "Show me a dangerous command"},
    )

    # Set up event listening
    events: queue.Queue[dict[str, Any]] = queue.Queue()
    tool_id = None

    def listen_for_events():
        nonlocal tool_id
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
                        if event_data.get("type") == "tool_pending":
                            tool_id = event_data.get("tool_id")
        except Exception as e:
            events.put({"error": str(e)})
        finally:
            resp.close()

    event_thread = threading.Thread(target=listen_for_events)
    event_thread.daemon = True
    event_thread.start()
    time.sleep(1)  # Give time to connect

    # Mock tool detection
    def mock_iter_from_content(content):
        class MockToolUse:
            def __init__(self):
                self.is_runnable = True
                self.tool = "shell"
                self.args = ["rm", "-rf", "/"]

            def __str__(self):
                return "```shell\nrm -rf /\n```"

        yield MockToolUse()

    # Start generation
    with (
        unittest.mock.patch("gptme.server.api_v2._stream", mock_stream),
        unittest.mock.patch(
            "gptme.tools.ToolUse.iter_from_content", mock_iter_from_content
        ),
        # Also mock resume_generation to avoid Claude API errors
        unittest.mock.patch(
            "gptme.server.api_v2.resume_generation", lambda *args, **kwargs: None
        ),
    ):
        requests.post(
            f"http://localhost:{port}/api/v2/conversations/{conversation_id}/generate",
            json={"session_id": session_id, "model": "openai/mock-model"},
        )

        # Wait for tool_pending event
        timeout = 10
        start_time = time.time()
        while not tool_id and time.time() - start_time < timeout:
            time.sleep(0.1)

        assert tool_id is not None, "Did not receive tool_pending event"

        # Skip the tool execution
        response = requests.post(
            f"http://localhost:{port}/api/v2/conversations/{conversation_id}/tool/confirm",
            json={"session_id": session_id, "tool_id": tool_id, "action": "skip"},
        )
        assert response.status_code == 200

    # Wait for events
    timeout = 10
    start_time = time.time()
    received_events = []

    while time.time() - start_time < timeout:
        try:
            event = events.get(timeout=0.5)
            received_events.append(event)
            if any(e.get("type") == "tool_skipped" for e in received_events):
                # Wait a bit more to check for any continuation
                time.sleep(1)
                break
        except queue.Empty:
            continue

    # Verify events include tool_skipped
    event_types = [e.get("type") for e in received_events if "type" in e]
    assert "tool_pending" in event_types
    assert "tool_skipped" in event_types

    # Verify conversation state
    time.sleep(0.5)
    resp = requests.get(
        f"http://localhost:{port}/api/v2/conversations/{conversation_id}"
    )
    assert resp.status_code == 200

    conversation_data = resp.json()
    messages = conversation_data["log"]

    # Should have:
    # 1. System message
    # 2. User message
    # 3. Assistant message with tool use (might be truncated)
    # No tool output message since it was skipped
    assert len(messages) == 3, f"Expected 3 messages, got {len(messages)}: {messages}"

    # Check that assistant message exists with the right role
    assert messages[2]["role"] == "assistant", "Expected an assistant message"


@pytest.mark.timeout(30)  # Increased timeout for more realistic test
def test_minimal_mocking_real_tool_execution(server_thread):
    """
    Test with minimal mocking that uses a real shell command to validate the full tool execution flow.

    This test specifically verifies that:
    1. Messages are properly persisted after tool execution
    2. The proper sequence of events is sent to the client
    3. Tool execution actually works with real shell commands
    """
    # Get port from fixture
    port = server_thread

    # Create a conversation with a unique ID
    conversation_id = f"test-real-tool-{int(time.time())}"

    # Test identifier to make output unique and verifiable
    test_id = str(uuid.uuid4())[:8]
    echo_content = f"real-test-{test_id}"

    # Create conversation with system message
    resp = requests.put(
        f"http://localhost:{port}/api/v2/conversations/{conversation_id}",
        json={
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant for testing.",
                    "timestamp": datetime.now().isoformat(),
                }
            ]
        },
    )
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    # Add a user message requesting a simple shell command
    # Use a command that is safe, predictable, and available on all platforms
    requests.post(
        f"http://localhost:{port}/api/v2/conversations/{conversation_id}",
        json={
            "role": "user",
            "content": f"Please run the command: echo '{echo_content}'",
        },
    )

    # Track events
    events: queue.Queue[dict[str, Any]] = queue.Queue()
    tool_id = None
    tool_output_received = False
    event_sequence = []

    # Set up event listener
    def listen_for_events():
        nonlocal tool_id, tool_output_received, event_sequence
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

                        # Record event type for debugging
                        if "type" in event_data:
                            event_type = event_data["type"]
                            event_sequence.append(event_type)
                            logger.info(f"Received event: {event_type}")

                            # Track specific events
                            if event_type == "tool_pending":
                                tool_id = event_data.get("tool_id")
                                logger.info(f"Tool pending: {tool_id}")
                            elif event_type == "tool_output":
                                tool_output_received = True
                                logger.info(
                                    f"Tool output received: {event_data.get('content', '')[:30]}..."
                                )
        except Exception as e:
            logger.error(f"Event listener error: {e}")
            events.put({"error": str(e)})
        finally:
            resp.close()

    event_thread = threading.Thread(target=listen_for_events)
    event_thread.daemon = True
    event_thread.start()
    time.sleep(1)  # Wait for connection

    # Only mock the stream function to simulate a response with the tool
    # Everything else will use the real implementation
    def mock_stream(messages, model, tools=None, max_tokens=None):
        # Use the exact command from the user message for consistency
        cmd = f"echo '{echo_content}'"
        yield f"I'll run that command for you:\n\n```shell\n{cmd}\n```\n\n"
        yield f"This command will print '{echo_content}' to the console."

    # Start generation with minimal mocking
    with unittest.mock.patch("gptme.server.api_v2._stream", mock_stream):
        requests.post(
            f"http://localhost:{port}/api/v2/conversations/{conversation_id}/generate",
            json={"session_id": session_id, "model": "openai/mock-model"},
        )

        # Wait for tool_pending event
        timeout = 15
        start_time = time.time()
        while not tool_id and time.time() - start_time < timeout:
            time.sleep(0.1)

        assert tool_id is not None, "Did not receive tool_pending event"

        # Confirm the tool execution
        response = requests.post(
            f"http://localhost:{port}/api/v2/conversations/{conversation_id}/tool/confirm",
            json={"session_id": session_id, "tool_id": tool_id, "action": "confirm"},
        )
        assert response.status_code == 200

    # Wait for tool output with detailed logging
    timeout = 15
    start_time = time.time()
    while not tool_output_received and time.time() - start_time < timeout:
        time.sleep(0.1)
        if time.time() - start_time > timeout / 2 and not tool_output_received:
            logger.warning(
                f"Still waiting for tool_output event... Events so far: {event_sequence}"
            )

    assert (
        tool_output_received
    ), f"Did not receive tool_output event. Events received: {event_sequence}"

    # Wait a bit to ensure all operations complete
    time.sleep(2)

    # Check the conversation through the API
    resp = requests.get(
        f"http://localhost:{port}/api/v2/conversations/{conversation_id}"
    )
    assert resp.status_code == 200

    conversation_data = resp.json()
    messages = conversation_data["log"]

    # Log message data for debugging
    print("\nVerifying conversation messages:")
    for i, msg in enumerate(messages):
        print(f"{i}. {msg['role']}: {msg['content'][:50]}...")

    # We should have:
    # 1. System message (You are a helpful assistant)
    # 2. User message (Please run the command)
    # 3. Assistant message with tool use (I'll run that command + code block)
    # 4. System message with tool output (real test)
    assert len(messages) >= 4, f"Expected at least 4 messages, got {len(messages)}"

    # Verify message content
    assert messages[0]["role"] == "system"
    assert "helpful assistant" in messages[0]["content"]

    assert messages[1]["role"] == "user"
    assert "echo" in messages[1]["content"]
    assert echo_content in messages[1]["content"]

    # Third message should be from assistant and include the shell command
    assert messages[2]["role"] == "assistant"
    assert "shell" in messages[2]["content"]
    assert "echo" in messages[2]["content"]

    # Fourth message should be the tool output
    assert messages[3]["role"] == "system"
    assert (
        echo_content in messages[3]["content"]
    ), f"Expected '{echo_content}' in output: {messages[3]['content']}"

    # Check directly using LogManager as well to verify full persistence
    log_manager = LogManager.load(conversation_id, lock=False)
    log_messages = log_manager.log.messages

    # Validate the same assertions on the actual log
    assert (
        len(log_messages) >= 4
    ), f"Log manager shows fewer than 4 messages: {len(log_messages)}"
    assert log_messages[2].role == "assistant"
    assert "echo" in log_messages[2].content
    assert log_messages[3].role == "system"
    assert (
        echo_content in log_messages[3].content
    ), f"Expected '{echo_content}' in LogManager output: {log_messages[3].content}"

    # Print event sequence for debugging
    print(f"Final event sequence: {event_sequence}")

    # Verify event sequence has the expected ordering
    assert "tool_pending" in event_sequence, "Missing tool_pending event"
    assert "tool_executing" in event_sequence, "Missing tool_executing event"
    assert "tool_output" in event_sequence, "Missing tool_output event"

    pending_idx = event_sequence.index("tool_pending")
    executing_idx = event_sequence.index("tool_executing")
    output_idx = event_sequence.index("tool_output")

    assert pending_idx < executing_idx < output_idx, "Event sequence order is incorrect"


@pytest.mark.timeout(30)
def test_tool_confirmation_event_sequence(server_thread):
    """Test to specifically verify the sequence of events after tool confirmation."""
    # Get port from fixture
    port = server_thread

    # Create a conversation with a unique ID
    conversation_id = f"test-tool-events-{int(time.time())}"

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
        json={"role": "user", "content": "Run echo 'test'"},
    )

    # Prepare to track events
    events: queue.Queue[dict[str, Any]] = queue.Queue()
    tool_id = None
    received_tool_executing = False
    received_tool_output = False

    # Set up a very clear way to track the timing of events
    event_sequence = []

    # Start a thread to listen for events
    def listen_for_events():
        nonlocal tool_id, received_tool_executing, received_tool_output, event_sequence
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

                        # Record the event type in our sequence
                        if "type" in event_data:
                            event_sequence.append(event_data["type"])

                        # Track key events
                        if event_data.get("type") == "tool_pending":
                            tool_id = event_data.get("tool_id")
                        elif event_data.get("type") == "tool_executing":
                            received_tool_executing = True
                        elif event_data.get("type") == "tool_output":
                            received_tool_output = True
        except Exception as e:
            events.put({"error": str(e)})
            event_sequence.append(f"error: {str(e)}")
        finally:
            resp.close()

    event_thread = threading.Thread(target=listen_for_events)
    event_thread.daemon = True
    event_thread.start()
    time.sleep(1)  # Give time to connect

    # Mock stream to generate a simple tool use
    def mock_stream(
        messages, model, tools=None, max_tokens=None
    ) -> Generator[str, None, None]:
        # Return all content in one chunk to ensure it's stored properly
        yield "I'll run that command for you:\n\n```shell\necho 'test'\n```"

    # Mock the tool detection
    def mock_iter_from_content(content):
        # Only detect the tool once we have the full command sequence
        if "```shell\necho 'test'\n```" in content:

            class MockToolUse:
                def __init__(self):
                    self.is_runnable = True
                    self.tool = "shell"
                    self.args = ["echo", "'test'"]

                def __str__(self):
                    return "```shell\necho 'test'\n```"

                def execute(self, *args, **kwargs):
                    time.sleep(0.5)  # Simulate some execution time
                    yield Message("system", "test")

            yield MockToolUse()

    # Start generation
    with (
        unittest.mock.patch("gptme.server.api_v2._stream", mock_stream),
        unittest.mock.patch(
            "gptme.tools.ToolUse.iter_from_content", mock_iter_from_content
        ),
    ):
        requests.post(
            f"http://localhost:{port}/api/v2/conversations/{conversation_id}/generate",
            json={"session_id": session_id, "model": "openai/mock-model"},
        )

        # Wait for tool_pending event
        timeout = 10
        start_time = time.time()
        while not tool_id and time.time() - start_time < timeout:
            time.sleep(0.1)

        assert tool_id is not None, "Did not receive tool_pending event"

        # Record the timestamp before confirmation
        before_confirm = time.time()

        # Confirm the tool execution
        response = requests.post(
            f"http://localhost:{port}/api/v2/conversations/{conversation_id}/tool/confirm",
            json={"session_id": session_id, "tool_id": tool_id, "action": "confirm"},
        )

        # Record timestamp after confirmation
        after_confirm = time.time()

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    # Wait with an explicit timeout for both tool_executing and tool_output events
    tool_events_timeout = 10
    start_time = time.time()

    while time.time() - start_time < tool_events_timeout:
        if received_tool_executing and received_tool_output:
            break
        time.sleep(0.1)

    # Verify we got all the expected events
    assert received_tool_executing, "Did not receive tool_executing event"
    assert received_tool_output, "Did not receive tool_output event"

    # Verify the event sequence is correct - we should see tool_pending before confirm,
    # and tool_executing and tool_output after confirm
    pending_index = (
        event_sequence.index("tool_pending") if "tool_pending" in event_sequence else -1
    )
    executing_index = (
        event_sequence.index("tool_executing")
        if "tool_executing" in event_sequence
        else -1
    )
    output_index = (
        event_sequence.index("tool_output") if "tool_output" in event_sequence else -1
    )

    assert pending_index >= 0, "tool_pending event not found in sequence"
    assert executing_index >= 0, "tool_executing event not found in sequence"
    assert output_index >= 0, "tool_output event not found in sequence"

    assert (
        executing_index > pending_index
    ), "tool_executing should come after tool_pending"
    assert (
        output_index > executing_index
    ), "tool_output should come after tool_executing"

    # Verify the conversation reflects the execution
    resp = requests.get(
        f"http://localhost:{port}/api/v2/conversations/{conversation_id}"
    )
    assert resp.status_code == 200

    conversation_data = resp.json()
    messages = conversation_data["log"]

    # Should have:
    # 1. System message
    # 2. User message
    # 3. Assistant message with tool use
    # 4. System message with tool output
    assert len(messages) == 4, f"Expected 4 messages, got {len(messages)}"

    # Check that we have both the assistant message with tool use and the system message with output
    assert messages[2]["role"] == "assistant"
    assert "echo" in messages[2]["content"].lower(), messages[2]

    assert messages[3]["role"] == "system"
    assert "test" in messages[3]["content"]

    # For debugging possible issues, print the full event sequence
    print(f"\nEvent sequence: {event_sequence}")
    print(
        f"Time between confirmation request and response: {after_confirm - before_confirm:.3f}s"
    )
