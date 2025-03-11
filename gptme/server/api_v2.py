"""
V2 API for gptme server with improved control flow and tool execution management.

Key improvements:
- Session management for tracking active operations
- Separate event stream for different types of events
- Tool confirmation workflow
- Better interruption handling
"""

import logging
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from itertools import islice
from pathlib import Path
from typing import Any
from collections.abc import Generator

import flask
from flask import request

from ..dirs import get_logs_dir
from ..llm import _stream
from ..llm.models import get_default_model
from ..logmanager import LogManager, get_user_conversations, prepare_messages
from ..message import Message
from ..tools import ToolUse, execute_msg, init_tools

logger = logging.getLogger(__name__)

v2_api = flask.Blueprint("v2_api", __name__)


# Session Management
# ------------------


class ToolStatus(Enum):
    """Status of a tool execution."""

    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class ToolExecution:
    """Tracks a tool execution."""

    id: str
    tool: str
    args: list[str]
    content: str
    status: ToolStatus = ToolStatus.PENDING
    result: str | None = None
    auto_confirm: bool = False
    edited_content: str | None = None


@dataclass
class ConversationSession:
    """Session for a conversation."""

    id: str
    conversation_id: str
    active: bool = True
    generating: bool = False
    last_activity: datetime = field(default_factory=datetime.now)
    events: list[dict[str, Any]] = field(default_factory=list)
    pending_tools: dict[str, ToolExecution] = field(default_factory=dict)
    auto_confirm_count: int = 0
    clients: set[str] = field(default_factory=set)


class SessionManager:
    """Manages conversation sessions."""

    _sessions: dict[str, ConversationSession] = {}
    _conversation_sessions: dict[str, set[str]] = defaultdict(set)

    @classmethod
    def create_session(cls, conversation_id: str) -> ConversationSession:
        """Create a new session for a conversation."""
        session_id = str(uuid.uuid4())
        session = ConversationSession(id=session_id, conversation_id=conversation_id)
        cls._sessions[session_id] = session
        cls._conversation_sessions[conversation_id].add(session_id)
        return session

    @classmethod
    def get_session(cls, session_id: str) -> ConversationSession | None:
        """Get a session by ID."""
        return cls._sessions.get(session_id)

    @classmethod
    def get_sessions_for_conversation(
        cls, conversation_id: str
    ) -> list[ConversationSession]:
        """Get all sessions for a conversation."""
        return [
            cls._sessions[sid]
            for sid in cls._conversation_sessions.get(conversation_id, set())
            if sid in cls._sessions
        ]

    @classmethod
    def add_event(cls, conversation_id: str, event: dict[str, Any]) -> None:
        """Add an event to all sessions for a conversation."""
        for session in cls.get_sessions_for_conversation(conversation_id):
            session.events.append(event)
            session.last_activity = datetime.now()

    @classmethod
    def clean_inactive_sessions(cls, max_age_minutes: int = 60) -> None:
        """Clean up inactive sessions."""
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        to_remove = []

        for session_id, session in cls._sessions.items():
            if session.last_activity < cutoff and not session.generating:
                to_remove.append(session_id)

        for session_id in to_remove:
            cls.remove_session(session_id)

    @classmethod
    def remove_session(cls, session_id: str) -> None:
        """Remove a session."""
        if session_id in cls._sessions:
            conversation_id = cls._sessions[session_id].conversation_id
            if conversation_id in cls._conversation_sessions:
                cls._conversation_sessions[conversation_id].discard(session_id)
                if not cls._conversation_sessions[conversation_id]:
                    del cls._conversation_sessions[conversation_id]
            del cls._sessions[session_id]


# API Endpoints
# ------------


@v2_api.route("/api/v2")
def api_root():
    """Root endpoint for the v2 API."""
    return flask.jsonify(
        {
            "message": "gptme v2 API",
            "documentation": "https://gptme.org/docs/server.html",
        }
    )


@v2_api.route("/api/v2/conversations")
def api_conversations():
    """List conversations."""
    limit = int(request.args.get("limit", 100))
    conversations = list(islice(get_user_conversations(), limit))
    return flask.jsonify(conversations)


@v2_api.route("/api/v2/conversations/<string:conversation_id>")
def api_conversation(conversation_id: str):
    """Get a conversation."""
    init_tools(None)  # FIXME: this is not thread-safe
    log = LogManager.load(conversation_id, lock=False)
    log_dict = log.to_dict(branches=True)

    # make all paths absolute or relative to workspace (no "../")
    for msg in log_dict["log"]:
        if files := msg.get("files"):
            msg["files"] = [
                (
                    str(path.relative_to(log.workspace))
                    if (path := Path(f).resolve()).is_relative_to(log.workspace)
                    else str(path)
                )
                for f in files
            ]
    return flask.jsonify(log_dict)


@v2_api.route("/api/v2/conversations/<string:conversation_id>", methods=["PUT"])
def api_conversation_put(conversation_id: str):
    """Create a new conversation."""
    msgs = []
    req_json = flask.request.json
    if req_json and "messages" in req_json:
        for msg in req_json["messages"]:
            timestamp: datetime = datetime.fromisoformat(msg["timestamp"])
            msgs.append(Message(msg["role"], msg["content"], timestamp=timestamp))

    logdir = get_logs_dir() / conversation_id
    if logdir.exists():
        return flask.jsonify(
            {"error": f"Conversation already exists: {conversation_id}"}
        ), 409

    logdir.mkdir(parents=True)
    log = LogManager(msgs, logdir=logdir)
    log.write()

    # Create a session for this conversation
    session = SessionManager.create_session(conversation_id)

    return flask.jsonify(
        {"status": "ok", "conversation_id": conversation_id, "session_id": session.id}
    )


@v2_api.route("/api/v2/conversations/<string:conversation_id>", methods=["POST"])
def api_conversation_post(conversation_id: str):
    """Append a message to a conversation."""
    req_json = flask.request.json
    if not req_json:
        return flask.jsonify({"error": "No JSON data provided"}), 400

    if "role" not in req_json or "content" not in req_json:
        return flask.jsonify({"error": "Missing required fields (role, content)"}), 400

    branch = req_json.get("branch", "main")
    tool_allowlist = req_json.get("tools", None)

    init_tools(tool_allowlist)  # FIXME: this is not thread-safe

    try:
        log = LogManager.load(conversation_id, branch=branch)
    except FileNotFoundError:
        return flask.jsonify(
            {"error": f"Conversation not found: {conversation_id}"}
        ), 404

    msg = Message(
        req_json["role"], req_json["content"], files=req_json.get("files", [])
    )
    log.append(msg)

    # Notify all sessions that a new message was added
    SessionManager.add_event(
        conversation_id,
        {
            "type": "message_added",
            "message": {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
            },
        },
    )

    return flask.jsonify({"status": "ok"})


@v2_api.route(
    "/api/v2/conversations/<string:conversation_id>/session", methods=["POST"]
)
def api_conversation_session(conversation_id: str):
    """Create a new session for a conversation."""
    # Check if conversation exists
    try:
        LogManager.load(conversation_id, lock=False)
    except FileNotFoundError:
        return flask.jsonify(
            {"error": f"Conversation not found: {conversation_id}"}
        ), 404

    # Create a new session
    session = SessionManager.create_session(conversation_id)

    return flask.jsonify({"status": "ok", "session_id": session.id})


@v2_api.route("/api/v2/conversations/<string:conversation_id>/events")
def api_conversation_events(conversation_id: str):
    """Subscribe to conversation events."""
    session_id = request.args.get("session_id")
    if not session_id:
        # Create a new session if none provided
        session = SessionManager.create_session(conversation_id)
        session_id = session.id
    else:
        session_obj = SessionManager.get_session(session_id)
        if session_obj is None:
            return flask.jsonify({"error": f"Session not found: {session_id}"}), 404
        session = session_obj

    # Generate event stream
    def generate_events() -> Generator[str, None, None]:
        try:
            # Add this client to the session
            client_id = str(uuid.uuid4())
            session.clients.add(client_id)

            # Send initial connection event
            yield f"data: {flask.json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"

            # Create an event queue
            last_event_index = 0

            while True:
                # Check if there are new events
                if last_event_index < len(session.events):
                    # Send any new events
                    for event in session.events[last_event_index:]:
                        yield f"data: {flask.json.dumps(event)}\n\n"
                    last_event_index = len(session.events)

                # Wait a bit before checking again
                yield f"data: {flask.json.dumps({'type': 'ping'})}\n\n"
                # In a real implementation, use asyncio or similar for better performance
                # For this example, just sleep briefly
                time.sleep(1)

        except GeneratorExit:
            # Client disconnected
            if session:
                session.clients.discard(client_id)
                if not session.clients:
                    # If no clients are connected, mark the session for cleanup
                    session.active = False
            raise

    return flask.Response(
        generate_events(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable buffering in nginx
        },
    )


@v2_api.route(
    "/api/v2/conversations/<string:conversation_id>/generate", methods=["POST"]
)
def api_conversation_generate(conversation_id: str):
    """Start generation of a response."""
    req_json = flask.request.json or {}
    session_id = req_json.get("session_id")

    if not session_id:
        return flask.jsonify({"error": "session_id is required"}), 400

    session = SessionManager.get_session(session_id)
    if session is None:
        return flask.jsonify({"error": f"Session not found: {session_id}"}), 404

    if session.generating:
        return flask.jsonify({"error": "Generation already in progress"}), 409

    # Start generation in a background thread
    def generate_response_thread():
        try:
            # Mark session as generating
            session.generating = True

            # Get the branch and model
            branch = req_json.get("branch", "main")
            default_model = get_default_model()
            assert (
                default_model is not None
            ), "No model loaded and no model specified in request"
            model = req_json.get("model", default_model.full)

            # Load conversation
            manager = LogManager.load(
                conversation_id,
                branch=branch,
                lock=False,
            )

            # Prepare messages for the model
            msgs = prepare_messages(manager.log.messages)
            if not msgs:
                SessionManager.add_event(
                    conversation_id,
                    {"type": "error", "error": "No messages to process"},
                )
                session.generating = False
                return

            # Notify clients that generation is starting
            SessionManager.add_event(conversation_id, {"type": "generation_started"})

            # Stream tokens from the model
            output = ""
            for token in (
                char for chunk in _stream(msgs, model, tools=None) for char in chunk
            ):
                output += token

                # Send token to clients
                SessionManager.add_event(
                    conversation_id, {"type": "generation_progress", "token": token}
                )

                # Check for complete tool uses
                tooluses = list(ToolUse.iter_from_content(output))
                if tooluses and any(tooluse.is_runnable for tooluse in tooluses):
                    # Handle tool use
                    for tooluse in tooluses:
                        if tooluse.is_runnable:
                            # Create a tool execution record
                            tool_id = str(uuid.uuid4())
                            # Get tool details from the ToolUse object
                            # Since we don't know exact ToolUse API, use safe fallbacks
                            tool_name = (
                                getattr(tooluse, "tool", "")
                                or tooluse.__class__.__name__
                            )
                            tool_args = getattr(tooluse, "args", []) or []
                            raw_content = str(tooluse)  # Use string representation

                            tool_exec = ToolExecution(
                                id=tool_id,
                                tool=tool_name,
                                args=tool_args,
                                content=raw_content,
                                auto_confirm=session.auto_confirm_count > 0,
                            )
                            session.pending_tools[tool_id] = tool_exec

                            # Notify about pending tool
                            SessionManager.add_event(
                                conversation_id,
                                {
                                    "type": "tool_pending",
                                    "tool_id": tool_id,
                                    "tool": tool_name,
                                    "args": tool_args,
                                    "content": raw_content,
                                    "auto_confirm": tool_exec.auto_confirm,
                                },
                            )

                            # If auto-confirm is enabled, execute the tool
                            if tool_exec.auto_confirm:
                                session.auto_confirm_count -= 1
                                await_tool_execution(
                                    conversation_id, session, tool_id, tooluse
                                )
                            else:
                                # Wait for confirmation
                                session.generating = False
                                return

                    break

            # Store the complete message if we reached here (no tools to execute)
            msg = Message("assistant", output)
            msg = msg.replace(quiet=True)
            manager.append(msg)

            # Notify clients that generation is complete
            SessionManager.add_event(
                conversation_id,
                {
                    "type": "generation_complete",
                    "message": {
                        "role": "assistant",
                        "content": output,
                        "timestamp": msg.timestamp.isoformat(),
                    },
                },
            )

            # Mark session as not generating
            session.generating = False

        except Exception as e:
            logger.exception(f"Error during generation: {e}")
            SessionManager.add_event(
                conversation_id, {"type": "error", "error": str(e)}
            )
            session.generating = False

    # Start generation in a thread
    thread = threading.Thread(target=generate_response_thread)
    thread.daemon = True
    thread.start()

    return flask.jsonify(
        {"status": "ok", "message": "Generation started", "session_id": session_id}
    )


@v2_api.route(
    "/api/v2/conversations/<string:conversation_id>/tool/confirm", methods=["POST"]
)
def api_conversation_tool_confirm(conversation_id: str):
    """Confirm or modify a tool execution."""
    req_json = flask.request.json or {}
    session_id = req_json.get("session_id")
    tool_id = req_json.get("tool_id")
    action = req_json.get("action")

    if not session_id or not tool_id or not action:
        return flask.jsonify(
            {"error": "session_id, tool_id, and action are required"}
        ), 400

    session = SessionManager.get_session(session_id)
    if session is None:
        return flask.jsonify({"error": f"Session not found: {session_id}"}), 404

    if tool_id not in session.pending_tools:
        return flask.jsonify({"error": f"Tool not found: {tool_id}"}), 404

    tool_exec = session.pending_tools[tool_id]

    if action == "confirm":
        # Execute the tool
        tooluses = list(ToolUse.iter_from_content(tool_exec.content))
        for tooluse in tooluses:
            if tooluse.is_runnable:
                await_tool_execution(conversation_id, session, tool_id, tooluse)
                break

    elif action == "edit":
        # Edit and then execute the tool
        edited_content = req_json.get("content")
        if not edited_content:
            return flask.jsonify({"error": "content is required for edit action"}), 400

        tool_exec.edited_content = edited_content

        # Execute with edited content
        # In a real implementation, parse the edited content to create a new ToolUse
        # For this example, just use a placeholder
        await_tool_execution(conversation_id, session, tool_id, None, edited_content)

    elif action == "skip":
        # Skip the tool execution
        tool_exec.status = ToolStatus.SKIPPED
        del session.pending_tools[tool_id]

        SessionManager.add_event(
            conversation_id, {"type": "tool_skipped", "tool_id": tool_id}
        )

        # Resume generation
        resume_generation(conversation_id, session)

    elif action == "auto":
        # Enable auto-confirmation for future tools
        count = req_json.get("count", 1)
        if count <= 0:
            return flask.jsonify({"error": "count must be positive"}), 400

        session.auto_confirm_count = count

        # Also confirm this tool
        tooluses = list(ToolUse.iter_from_content(tool_exec.content))
        for tooluse in tooluses:
            if tooluse.is_runnable:
                await_tool_execution(conversation_id, session, tool_id, tooluse)
                break

    else:
        return flask.jsonify({"error": f"Unknown action: {action}"}), 400

    return flask.jsonify({"status": "ok", "message": f"Tool {action}ed"})


@v2_api.route(
    "/api/v2/conversations/<string:conversation_id>/interrupt", methods=["POST"]
)
def api_conversation_interrupt(conversation_id: str):
    """Interrupt the current generation or tool execution."""
    req_json = flask.request.json or {}
    session_id = req_json.get("session_id")

    if not session_id:
        return flask.jsonify({"error": "session_id is required"}), 400

    session = SessionManager.get_session(session_id)
    if session is None:
        return flask.jsonify({"error": f"Session not found: {session_id}"}), 404

    if not session.generating and not session.pending_tools:
        return flask.jsonify(
            {"error": "No active generation or tool execution to interrupt"}
        ), 400

    # Mark session as not generating
    session.generating = False

    # Clear pending tools
    session.pending_tools.clear()

    # Notify about interruption
    SessionManager.add_event(conversation_id, {"type": "interrupted"})

    return flask.jsonify({"status": "ok", "message": "Interrupted"})


# Helper functions
# ---------------


def await_tool_execution(
    conversation_id: str,
    session: ConversationSession,
    tool_id: str,
    tooluse: ToolUse | None,
    edited_content: str | None = None,
):
    """Execute a tool and handle its output."""

    # This function would ideally run asynchronously to not block the request
    # For simplicity, we'll run it in a thread
    def execute_tool_thread():
        try:
            tool_exec = session.pending_tools[tool_id]
            tool_exec.status = ToolStatus.EXECUTING

            # Notify about tool execution
            SessionManager.add_event(
                conversation_id, {"type": "tool_executing", "tool_id": tool_id}
            )

            # Load the conversation
            manager = LogManager.load(conversation_id, lock=False)

            if tooluse:
                # Create message with the tool use
                msg = Message("assistant", tool_exec.content)
                msg = msg.replace(quiet=True)
                manager.append(msg)

                # Execute the tool
                try:
                    if edited_content:
                        # Create a new message with the edited content
                        edit_msg = Message(
                            "system", f"[Tool execution was edited]\n\n{edited_content}"
                        )
                        manager.append(edit_msg)

                        # Try to parse the edited content as a tool use
                        edited_tooluses = list(
                            ToolUse.iter_from_content(edited_content)
                        )
                        if edited_tooluses and any(
                            tu.is_runnable for tu in edited_tooluses
                        ):
                            # Execute the edited tool use without needing to extract the specific tooluse
                            edited_msg = Message("assistant", edited_content)
                            tool_outputs = list(execute_msg(edited_msg, lambda _: True))
                        else:
                            # Cannot parse the edited content
                            tool_outputs = []
                            tool_exec.result = (
                                "Could not parse edited content as a valid tool use"
                            )
                            tool_exec.status = ToolStatus.FAILED
                    else:
                        # Execute the original tool
                        tool_outputs = list(execute_msg(msg, lambda _: True))

                    # Store the tool outputs
                    for tool_output in tool_outputs:
                        manager.append(tool_output)

                        # Notify about tool output
                        SessionManager.add_event(
                            conversation_id,
                            {
                                "type": "tool_output",
                                "tool_id": tool_id,
                                "output": {
                                    "role": tool_output.role,
                                    "content": tool_output.content,
                                    "timestamp": tool_output.timestamp.isoformat(),
                                },
                            },
                        )

                    if tool_outputs:
                        tool_exec.result = "\n".join(
                            out.content for out in tool_outputs
                        )
                        tool_exec.status = ToolStatus.COMPLETED
                    else:
                        tool_exec.result = "Tool execution completed with no output"
                        tool_exec.status = ToolStatus.COMPLETED

                except Exception as e:
                    logger.exception(
                        f"Error executing tool {tooluse.__class__.__name__}"
                    )
                    tool_exec.result = f"Error: {str(e)}"
                    tool_exec.status = ToolStatus.FAILED

                    # Notify about tool failure
                    SessionManager.add_event(
                        conversation_id,
                        {"type": "tool_failed", "tool_id": tool_id, "error": str(e)},
                    )

            # Remove the tool from pending
            if tool_id in session.pending_tools:
                del session.pending_tools[tool_id]

            # Resume generation if needed
            if not session.pending_tools:
                resume_generation(conversation_id, session)

        except Exception as e:
            logger.exception(f"Error in tool execution thread: {e}")
            SessionManager.add_event(
                conversation_id,
                {
                    "type": "error",
                    "error": f"Internal error during tool execution: {str(e)}",
                },
            )
            session.generating = False

    # Start execution in a thread
    thread = threading.Thread(target=execute_tool_thread)
    thread.daemon = True
    thread.start()


def resume_generation(conversation_id: str, session: ConversationSession):
    """Resume generation after tool execution."""

    # Start the generation in a background thread
    def generate_response_thread():
        try:
            # Mark session as generating
            session.generating = True

            # Notify clients that generation is resuming
            SessionManager.add_event(conversation_id, {"type": "generation_resuming"})

            # Load the conversation manager
            manager = LogManager.load(
                conversation_id,
                lock=False,
            )

            # Get the default model
            default_model = get_default_model()
            assert default_model is not None, "No model loaded and no model specified"
            model = default_model.full

            # Prepare messages for the model
            msgs = prepare_messages(manager.log.messages)
            if not msgs:
                SessionManager.add_event(
                    conversation_id,
                    {"type": "error", "error": "No messages to process"},
                )
                session.generating = False
                return

            # Stream tokens from the model
            output = ""
            for token in (
                char for chunk in _stream(msgs, model, tools=None) for char in chunk
            ):
                output += token

                # Send token to clients
                SessionManager.add_event(
                    conversation_id, {"type": "generation_progress", "token": token}
                )

                # Check for complete tool uses
                tooluses = list(ToolUse.iter_from_content(output))
                if tooluses and any(tooluse.is_runnable for tooluse in tooluses):
                    # Handle tool use
                    for tooluse in tooluses:
                        if tooluse.is_runnable:
                            # Create a tool execution record
                            tool_id = str(uuid.uuid4())
                            # Get tool details from the ToolUse object
                            tool_name = (
                                tooluse.__class__.__name__
                            )  # Use class name as fallback
                            tool_args: list[str] = []  # Default to empty args list
                            raw_content = str(tooluse)  # Use string representation

                            tool_exec = ToolExecution(
                                id=tool_id,
                                tool=tool_name,
                                args=tool_args,
                                content=raw_content,
                                auto_confirm=session.auto_confirm_count > 0,
                            )
                            session.pending_tools[tool_id] = tool_exec

                            # Notify about pending tool
                            SessionManager.add_event(
                                conversation_id,
                                {
                                    "type": "tool_pending",
                                    "tool_id": tool_id,
                                    "tool": tool_name,
                                    "args": tool_args,
                                    "content": raw_content,
                                    "auto_confirm": tool_exec.auto_confirm,
                                },
                            )

                            # If auto-confirm is enabled, execute the tool
                            if tool_exec.auto_confirm:
                                session.auto_confirm_count -= 1
                                await_tool_execution(
                                    conversation_id, session, tool_id, tooluse
                                )
                            else:
                                # Wait for confirmation
                                session.generating = False
                                return

                    break

            # Store the complete message if we reached here (no more tools to execute)
            msg = Message("assistant", output)
            msg = msg.replace(quiet=True)
            manager.append(msg)

            # Notify clients that generation is complete
            SessionManager.add_event(
                conversation_id,
                {
                    "type": "generation_complete",
                    "message": {
                        "role": "assistant",
                        "content": output,
                        "timestamp": msg.timestamp.isoformat(),
                    },
                },
            )

            # Mark session as not generating
            session.generating = False

        except Exception as e:
            logger.exception(f"Error resuming generation: {e}")
            SessionManager.add_event(
                conversation_id, {"type": "error", "error": str(e)}
            )
            session.generating = False

    # Start generation in a thread
    thread = threading.Thread(target=generate_response_thread)
    thread.daemon = True
    thread.start()
