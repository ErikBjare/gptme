import pytest
from flask.testing import FlaskClient
from gptme.server import create_app


@pytest.fixture
def client():
    app = create_app()
    with app.test_client() as client:
        yield client


def test_api_root(client: FlaskClient):
    response = client.get("/api")
    assert response.status_code == 200
    assert response.get_json() == {"message": "Hello World!"}


def test_api_conversations(client: FlaskClient):
    # TODO: Add setup for conversations
    response = client.get("/api/conversations")
    assert response.status_code == 200
    # TODO: Add assertions for the response


# def test_api_conversation(client: FlaskClient):
#     # TODO: Add setup for a conversation
#     response = client.get("/api/conversations/<path:logfile>")
#     assert response.status_code == 200
#     # TODO: Add assertions for the response

# def test_api_conversation_put(client: FlaskClient):
#     # TODO: Add setup for a conversation
#     response = client.put("/api/conversations/<path:logfile>", json={})
#     assert response.status_code == 200
#     # TODO: Add assertions for the response

# def test_api_conversation_post(client: FlaskClient):
#     # TODO: Add setup for a conversation
#     response = client.post("/api/conversations/<path:logfile>", json={})
#     assert response.status_code == 200
#     # TODO: Add assertions for the response

# def test_api_conversation_generate(client: FlaskClient):
#     # TODO: Add setup for a conversation
#     response = client.post("/api/conversations/<path:logfile>/generate", json={})
#     assert response.status_code == 200
#     # TODO: Add assertions for the response

# def test_static_proxy(client: FlaskClient):
#     # TODO: Add setup for static files
#     response = client.get("/static/<path:path>")
#     assert response.status_code == 200
#     # TODO: Add assertions for the response


def test_root(client: FlaskClient):
    response = client.get("/")
    assert response.status_code == 200
    # TODO: Add assertions for the response
