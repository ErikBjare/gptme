"""
Serve web UI and API for the application.

See here for instructions how to serve matplotlib figures:
 - https://matplotlib.org/stable/gallery/user_interfaces/web_application_server_sgskip.html
"""

import atexit
import io
from contextlib import redirect_stdout
from datetime import datetime
from importlib import resources
from itertools import islice

import flask
from flask import current_app, request

from ..commands import execute_cmd
from ..dirs import get_logs_dir
from ..llm import reply
from ..logmanager import LogManager, get_user_conversations, prepare_messages
from ..message import Message
from ..models import get_model
from ..tools import execute_msg

api = flask.Blueprint("api", __name__)


@api.route("/api")
def api_root():
    return flask.jsonify({"message": "Hello World!"})


@api.route("/api/conversations")
def api_conversations():
    limit = int(request.args.get("limit", 100))
    conversations = list(islice(get_user_conversations(), limit))
    return flask.jsonify(conversations)


@api.route("/api/conversations/<path:logfile>")
def api_conversation(logfile: str):
    """Get a conversation."""
    log = LogManager.load(logfile)
    return flask.jsonify(log.to_dict(branches=True))


@api.route("/api/conversations/<path:logfile>", methods=["PUT"])
def api_conversation_put(logfile: str):
    """Create or update a conversation."""
    msgs = []
    req_json = flask.request.json
    if req_json and "messages" in req_json:
        for msg in req_json["messages"]:
            timestamp: datetime = datetime.fromisoformat(msg["timestamp"])
            msgs.append(Message(msg["role"], msg["content"], timestamp=timestamp))

    logdir = get_logs_dir() / logfile
    if logdir.exists():
        raise ValueError(f"Conversation already exists: {logdir.name}")
    logdir.mkdir(parents=True)
    log = LogManager(msgs, logdir=logdir)
    log.write()
    return {"status": "ok"}


@api.route(
    "/api/conversations/<path:logfile>",
    methods=["POST"],
)
def api_conversation_post(logfile: str):
    """Post a message to the conversation."""
    req_json = flask.request.json
    branch = (req_json or {}).get("branch", "main")
    log = LogManager.load(logfile, branch=branch)
    assert req_json
    assert "role" in req_json
    assert "content" in req_json
    msg = Message(
        req_json["role"], req_json["content"], files=req_json.get("files", [])
    )
    log.append(msg)
    return {"status": "ok"}


# TODO: add support for confirmation
def confirm_func(msg: str) -> bool:
    return True


# generate response
@api.route("/api/conversations/<path:logfile>/generate", methods=["POST"])
def api_conversation_generate(logfile: str):
    # get model or use server default
    req_json = flask.request.json or {}
    model = req_json.get("model", get_model().model)

    # load conversation
    manager = LogManager.load(logfile, branch=req_json.get("branch", "main"))

    # if prompt is a user-command, execute it
    if manager.log[-1].role == "user":
        # TODO: capture output of command and return it

        f = io.StringIO()
        print("Begin capturing stdout, to pass along command output.")
        with redirect_stdout(f):
            resp = execute_cmd(manager.log[-1], manager, confirm_func)
        print("Done capturing stdout.")
        if resp:
            manager.write()
            output = f.getvalue()
            return flask.jsonify(
                [{"role": "system", "content": output, "stored": False}]
            )

    # performs reduction/context trimming, if necessary
    msgs = prepare_messages(manager.log.messages)

    # generate response
    # TODO: add support for streaming
    msg = reply(msgs, model=model, stream=True)
    msg = msg.replace(quiet=True)

    # log response and run tools
    resp_msgs = []
    manager.append(msg)
    resp_msgs.append(msg)
    for reply_msg in execute_msg(msg, confirm_func):
        manager.append(reply_msg)
        resp_msgs.append(reply_msg)

    return flask.jsonify(
        [{"role": msg.role, "content": msg.content} for msg in resp_msgs]
    )


gptme_path_ctx = resources.as_file(resources.files("gptme"))
root_path = gptme_path_ctx.__enter__()
static_path = root_path / "server" / "static"
media_path = root_path.parent / "media"
atexit.register(gptme_path_ctx.__exit__, None, None, None)


# serve index.html from the root
@api.route("/")
def root():
    return current_app.send_static_file("index.html")


@api.route("/favicon.png")
def favicon():
    return flask.send_from_directory(media_path, "logo.png")


def create_app() -> flask.Flask:
    """Create the Flask app."""
    app = flask.Flask(__name__, static_folder=static_path)
    app.register_blueprint(api)
    return app
