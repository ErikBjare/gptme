"""
Serve web UI and API for the application.

See here for instructions how to serve matplotlib figures:
 - https://matplotlib.org/stable/gallery/user_interfaces/web_application_server_sgskip.html
"""

import io
from contextlib import redirect_stdout

import flask

from .commands import execute_cmd
from .dirs import get_logs_dir
from .llm import reply
from .logmanager import LogManager, get_conversations
from .message import Message
from .models import get_model
from .tools import execute_msg

api = flask.Blueprint("api", __name__)


@api.route("/api")
def api_root():
    return flask.jsonify({"message": "Hello World!"})


@api.route("/api/conversations")
def api_conversations():
    conversations = list(get_conversations())
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
            msgs.append(
                Message(msg["role"], msg["content"], timestamp=msg["timestamp"])
            )

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
    msg = Message(req_json["role"], req_json["content"])
    log.append(msg)
    return {"status": "ok"}


# generate response
@api.route("/api/conversations/<path:logfile>/generate", methods=["POST"])
def api_conversation_generate(logfile: str):
    # get model or use server default
    req_json = flask.request.json or {}
    model = req_json.get("model", get_model()["model"])

    # load conversation
    log = LogManager.load(logfile, branch=req_json.get("branch", "main"))

    # if prompt is a user-command, execute it
    if log[-1].role == "user":
        # TODO: capture output of command and return it

        f = io.StringIO()
        print("Begin capturing stdout, to pass along command output.")
        with redirect_stdout(f):
            resp = execute_cmd(log[-1], log)
        print("Done capturing stdout.")
        if resp:
            log.write()
            output = f.getvalue()
            return flask.jsonify(
                [{"role": "system", "content": output, "stored": False}]
            )

    # performs reduction/context trimming, if necessary
    msgs = log.prepare_messages()

    # generate response
    # TODO: add support for streaming
    msg = reply(msgs, model=model, stream=True)
    msg.quiet = True

    # log response and run tools
    resp_msgs = []
    log.append(msg)
    resp_msgs.append(msg)
    for msg in execute_msg(msg, ask=False):
        log.append(msg)
        resp_msgs.append(msg)

    return flask.jsonify(
        [{"role": msg.role, "content": msg.content} for msg in resp_msgs]
    )


# serve the static assets in the static folder
@api.route("/static/<path:path>")
def static_proxy(path):
    return flask.send_from_directory("static", path)


# serve index.html from the root
@api.route("/")
def root():
    return flask.send_from_directory("../static", "index.html")


def create_app():
    app = flask.Flask(__name__, static_folder="../static")
    app.register_blueprint(api)

    return app


def main():
    app = create_app()
    app.run(debug=True)
