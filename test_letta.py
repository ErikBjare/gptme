# Import the LettaAgent class and the create_letta_agent function
from gptme.letta_integration import create_letta_agent

# Create an instance of LettaAgent
agent = create_letta_agent()

# Send a message to the agent
response = agent.send_message("Hello, Letta!")
print(response)

# Insert some memories into the archival memory
agent.insert_archival_memory("Learned about Python classes.")
agent.insert_archival_memory("Discussed AI capabilities.")
agent.insert_archival_memory("Explored memory management.")

# Search the archival memory
search_results = agent.search_archival_memory("AI")
print("Search Results:", search_results)
