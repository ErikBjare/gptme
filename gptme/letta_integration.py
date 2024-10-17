MAX_ARCHIVAL_MEMORY = 1000

class LettaAgent:
    def __init__(self, name, system):
        self.name = name
        self.system = system
        self.memory = {}
        self.archival_memory = []

    def send_message(self, message):
        if message is None:
            raise ValueError("Message cannot be None")
        return f"Received: {message}"

    def get_core_memory(self):
        return self.memory

    def get_archival_memory(self):
        return self.archival_memory

    def insert_archival_memory(self, memory):
        self.archival_memory.append(memory)
        if len(self.archival_memory) > MAX_ARCHIVAL_MEMORY:
            self.archival_memory.pop(0)

    def search_archival_memory(self, query):
        # Simple search implementation, can be improved with more sophisticated algorithms
        return [memory for memory in self.archival_memory if query.lower() in memory.lower()]

def create_letta_agent():
    return LettaAgent(
        name="GPTMe Agent",
        system="You are a helpful AI assistant with long-term memory capabilities. You can access and use information from previous interactions stored in your archival memory."
    )
