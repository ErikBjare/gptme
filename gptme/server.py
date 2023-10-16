"""
Serve web UI and API for the application.

See here for instructions how to serve matplotlib figures:
 - https://matplotlib.org/stable/gallery/user_interfaces/web_application_server_sgskip.html
"""

import flask

from .logmanager import LogManager, get_conversations

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


# serve the static assets in the static folder
@api.route("/static/<path:path>")
def static_proxy(path):
    print("serving static", path)
    return flask.send_from_directory("static", path)


# serve index.html from the root
@api.route("/")
def root():
    return flask.send_from_directory("static", "index.html")


def create_app():
    app = flask.Flask(__name__, static_folder="../static")
    app.register_blueprint(api)

    return app


def main():
    app = create_app()
    app.run(debug=True)
