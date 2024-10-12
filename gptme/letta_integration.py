class LettaAgent:
    def __init__(self, name, system):
        self.name = name
        self.system = system
        self.memory = {}

    def send_message(self, message):
        return f"Received: {message}"

    def get_core_memory(self):
        return self.memory

    def get_archival_memory(self):
        return []

    def insert_archival_memory(self, memory):
        pass

def create_letta_agent():
    return LettaAgent(
        "GPTMe Agent",
        "You are a helpful AI assistant."
    )
