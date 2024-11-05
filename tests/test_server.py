import random

import pytest

flask = pytest.importorskip(
    "flask", reason="flask not installed, install server extras (-E server)"
)

# noreorder
from flask.testing import FlaskClient  # fmt: skip
from gptme.init import init  # fmt: skip
from gptme.models import get_model  # fmt: skip
from gptme.server.api import create_app  # fmt: skip


@pytest.fixture(autouse=True)
def init_():
    init(None, interactive=False, tool_allowlist=None)


@pytest.fixture
def client():
    app = create_app()
    with app.test_client() as client:
        yield client


@pytest.fixture
def conv(client: FlaskClient):
    convname = f"test-server-{random.randint(0, 1000000)}"
    response = client.put(f"/api/conversations/{convname}", json={})
    assert response.status_code == 200
    return convname


def test_root(client: FlaskClient):
    response = client.get("/")
    assert response.status_code == 200


def test_api_root(client: FlaskClient):
    response = client.get("/api")
    assert response.status_code == 200
    assert response.get_json() == {"message": "Hello World!"}


def test_api_conversation_list(client: FlaskClient):
    response = client.get("/api/conversations")
    assert response.status_code == 200


def test_api_conversation_get(conv, client: FlaskClient):
    response = client.get(f"/api/conversations/{conv}")
    assert response.status_code == 200


def test_api_conversation_post(conv, client: FlaskClient):
    response = client.post(
        f"/api/conversations/{conv}",
        json={"role": "user", "content": "hello"},
    )
    assert response.status_code == 200


@pytest.mark.slow
def test_api_conversation_generate(conv: str, client: FlaskClient):
    # Ask the assistant to generate a test response
    response = client.post(
        f"/api/conversations/{conv}",
        json={"role": "user", "content": "hello, just testing"},
    )
    assert response.status_code == 200

    # Test regular (non-streaming) response
    response = client.post(
        f"/api/conversations/{conv}/generate",
        json={"model": get_model().model, "stream": False},
    )
    assert response.status_code == 200
    data = response.get_data(as_text=True)
    assert data  # Ensure we got some response
    msgs = response.get_json()
    assert msgs is not None  # Ensure we got valid JSON
    assert len(msgs) == 3  # Assistant message + 2 system messages from tool output

    # First message should be the assistant's response
    assert msgs[0]["role"] == "assistant"
    assert "thinking" in msgs[0]["content"]  # Should contain thinking tags

    # Next two messages should be system messages with tool output
    assert msgs[1]["role"] == "system"
    assert "ls" in msgs[1]["content"]
    assert msgs[2]["role"] == "system"
    assert "git status" in msgs[2]["content"]


@pytest.mark.slow
def test_api_conversation_generate_stream(conv: str, client: FlaskClient):
    # Ask the assistant to generate a test response
    response = client.post(
        f"/api/conversations/{conv}",
        json={"role": "user", "content": "hello, just testing"},
    )
    assert response.status_code == 200

    # Test streaming response
    response = client.post(
        f"/api/conversations/{conv}/generate",
        json={"model": get_model().model, "stream": True},
        headers={"Accept": "text/event-stream"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["Content-Type"]

    # Read and validate the streamed response
    chunks = list(response.iter_encoded())
    assert len(chunks) > 0

    # Each chunk should be a Server-Sent Event
    for chunk in chunks:
        chunk_str = chunk.decode("utf-8")
        assert chunk_str.startswith("data: ")
        # Skip empty chunks (heartbeats)
        if chunk_str.strip() == "data: ":
            continue
        data = chunk_str.replace("data: ", "").strip()
        assert data  # Non-empty data
