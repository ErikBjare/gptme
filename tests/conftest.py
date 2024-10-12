import pytest

@pytest.fixture
def language():
    return "python"

@pytest.fixture
def mock_client():
    class MockClient:
        def create_agent(self, name, system, llm_config, embedding_config):
            return MockAgent(name, system)

    return MockClient()

@pytest.fixture
def mock_agent(mock_client):
    return mock_client.create_agent(
        "Test Agent",
        "You are a helpful AI assistant for testing purposes.",
        None,
        None
    )

class MockAgent:
    def __init__(self, name, system):
        self.name = name
        self.system = system
        self.memory = {}

    def send_message(self, message):
        if message is None:
            raise ValueError("Message cannot be None")
        return f"Received: {message}"

    def get_core_memory(self):
        return self.memory

    def get_archival_memory(self):
        return []

    def insert_archival_memory(self, memory):
        pass
