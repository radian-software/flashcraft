import pathlib

import flask

RESOURCE_DIRECTORY = pathlib.Path(__file__).resolve().parent / "resources"

app = flask.Flask(__name__)


@app.route("/")
def route_index():
    return flask.send_from_directory(RESOURCE_DIRECTORY, "index.html")
