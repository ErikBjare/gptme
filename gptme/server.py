"""
Serve web UI and API for the application.

See here for instructions how to serve matplotlib figures:
 - https://matplotlib.org/stable/gallery/user_interfaces/web_application_server_sgskip.html
"""

import flask

from .commands import execute_cmd
from .llm import reply
from .logmanager import LogManager, get_conversations
from .message import Message
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
    log = LogManager.load(logfile)
    return flask.jsonify(log.to_dict())


@api.route(
    "/api/conversations/<path:logfile>",
    methods=["POST"],
)
def api_conversation_post(logfile: str):
    log = LogManager.load(logfile)
    req_json = flask.request.json
    assert req_json
    assert "role" in req_json
    assert "content" in req_json
    msg = Message(req_json["role"], req_json["content"])
    log.append(msg)
    return {"status": "ok"}


# generate response
@api.route("/api/conversations/<path:logfile>/generate", methods=["POST"])
def api_conversation_generate(logfile: str):
    # Lots copied from cli.py
    log = LogManager.load(logfile)

    # if prompt is a user-command, execute it
    if log[-1].role == "user":
        resp = execute_cmd(log[-1], log)
        if resp:
            log.write()
            return flask.jsonify({"response": resp})

    # performs reduction/context trimming, if necessary
    msgs = log.prepare_messages()

    # generate response
    # TODO: add support for streaming
    msg = reply(msgs, model="gpt-4", stream=True)
    msg.quiet = True

    # log response and run tools
    resp = [msg]
    print(msg)
    log.append(msg)
    for msg in execute_msg(msg, ask=False):
        print(msg)
        log.append(msg)

    return flask.jsonify([{"role": msg.role, "content": msg.content} for msg in resp])


# serve the static assets in the static folder
@api.route("/static/<path:path>")
def static_proxy(path):
    print("serving static", path)
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
