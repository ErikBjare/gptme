import pytest
from gptme.letta_integration import create_letta_agent, MAX_ARCHIVAL_MEMORY

def test_create_letta_agent():
    agent = create_letta_agent()
    assert agent is not None
    assert hasattr(agent, 'send_message')
    assert "long-term memory" in agent.system.lower()

def test_memory_management():
    agent = create_letta_agent()
    
    # Test core memory
    core_memory = agent.get_core_memory()
    assert isinstance(core_memory, dict)

    # Test archival memory
    archival_memory = agent.get_archival_memory()
    assert isinstance(archival_memory, list)

    # Test inserting archival memory
    agent.insert_archival_memory("Test memory")
    updated_archival_memory = agent.get_archival_memory()
    assert isinstance(updated_archival_memory, list)
    assert "Test memory" in updated_archival_memory

def test_agent_interaction():
    agent = create_letta_agent()
    response = agent.send_message("Hello, agent!")
    assert isinstance(response, str)
    assert len(response) > 0

def test_error_handling():
    agent = create_letta_agent()
    with pytest.raises(ValueError):
        agent.send_message(None)

def test_archival_memory_persistence():
    agent = create_letta_agent()
    agent.insert_archival_memory("Memory 1")
    agent.insert_archival_memory("Memory 2")
    
    # Simulate multiple interactions
    agent.send_message("Hello")
    agent.send_message("How are you?")
    
    archival_memory = agent.get_archival_memory()
    assert "Memory 1" in archival_memory
    assert "Memory 2" in archival_memory

def test_archival_memory_limit():
    agent = create_letta_agent()
    for i in range(MAX_ARCHIVAL_MEMORY + 10):
        agent.insert_archival_memory(f"Memory {i}")
    
    archival_memory = agent.get_archival_memory()
    assert len(archival_memory) == MAX_ARCHIVAL_MEMORY
    assert f"Memory {MAX_ARCHIVAL_MEMORY + 9}" in archival_memory
    assert "Memory 0" not in archival_memory

def test_search_archival_memory():
    agent = create_letta_agent()
    agent.insert_archival_memory("Apple is a fruit")
    agent.insert_archival_memory("Banana is yellow")
    agent.insert_archival_memory("Cherry is red")
    
    results = agent.search_archival_memory("fruit")
    assert len(results) == 1
    assert "Apple is a fruit" in results

    results = agent.search_archival_memory("is")
    assert len(results) == 3
