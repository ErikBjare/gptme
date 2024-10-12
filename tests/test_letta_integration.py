import pytest
from gptme.letta_integration import create_letta_agent

def test_create_letta_agent(mock_client):
    agent = create_letta_agent()
    assert agent is not None
    assert hasattr(agent, 'send_message')

def test_memory_management(mock_agent):
    # Test core memory
    core_memory = mock_agent.get_core_memory()
    assert isinstance(core_memory, dict)

    # Test archival memory
    archival_memory = mock_agent.get_archival_memory()
    assert isinstance(archival_memory, list)

    # Test inserting archival memory
    mock_agent.insert_archival_memory("Test memory")
    updated_archival_memory = mock_agent.get_archival_memory()
    assert isinstance(updated_archival_memory, list)

def test_agent_interaction(mock_agent):
    response = mock_agent.send_message("Hello, agent!")
    assert isinstance(response, str)
    assert len(response) > 0

def test_error_handling(mock_agent):
    with pytest.raises(Exception):  # Replace with specific exception if known
        mock_agent.send_message(None)  # or any invalid input
