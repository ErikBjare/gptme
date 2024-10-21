# Project Sidenotes

## 2023-05-10 (Current Date)

### New Session Started

- Initiated a new task session.
- Current project structure (based on environment details):

```
gptme/
├── eval/
│   └── run.py
├── server/
│   └── cli.py
├── tools/
│   └── tmux.py
└── init.py

train/
└── collect.py

.dockerignore
```

- Open files in VSCode:
  - .dockerignore
  - train/collect.py
  - gptme/eval/run.py
  - gptme/server/cli.py
  - gptme/tools/tmux.py
  - gptme/init.py

- Based on the information provided and the tasks outlined, here's a summary of the steps to integrate MemGPT-like memory management features into GPTMe:

## 2023-05-11 (Current Date)

### MemGPT Integration Plan

1. **MemGPT Memory Structure:**
   - Studied MemGPT's memory structure, which includes core memory, archival memory, and message history.
   - Core memory is divided into "human" and "persona" sections, each with a 2000 character limit.
   - Archival memory stores long-term information.
   - Conversation history tracks past interactions.

2. **Memory Management Functions:**
   - Created `GPTMeMemory` class with functions for core memory management, archival memory storage and retrieval, and message history tracking.
   - Implemented `core_memory_append`, `core_memory_replace`, `archival_memory_insert`, `archival_memory_search`, and `conversation_search` functions.

3. **Prompts.py Modification:**
   - Updated `prompts.py` to include new functions for memory management.
   - Integrated `GPTMeMemory` class and created wrapper functions for memory operations.
   - Modified `prompt_tools()` function to include descriptions of new memory management tools.

4. **Integration with Existing Structure:**
   - Integrated new memory functions with GPTMe's existing structure.
   - Updated `prompt_tools()` function to include new memory management capabilities.

5. **MemGPT Python Client Reference:**
   - Studied MemGPT's Python client documentation for standalone memory features.
   - Noted key findings about MemGPT's installation, configuration, and usage.
   - Outlined implementation steps for integrating MemGPT features into GPTMe.

6. **LTM State Save/Load Mechanism:**
   - Implemented mechanism to save and load LTM state in GPTMe.
   - Created `save_ltm_state` and `load_ltm_state` functions using JSON serialization.
   - Integrated save and load methods into the `GPTMe` class.

7. **System Prompt Update:**
   - Updated `prompt_gptme()` function to include instructions on using new memory management features.
   - Added explanations for `save_state()` and `load_state()` methods in the system prompt.

**Next Steps:**
- Implement the outlined changes in the codebase.
- Test the new memory management features thoroughly.
- Update documentation to reflect new capabilities.
- Consider performance optimizations for large-scale memory operations.

## 2023-05-12 (Current Date)

### GPTMe Class Analysis and MemGPT Integration Plan

1. **Current GPTMe Implementation:**
   - The `GPTMe` class in `agents.py` inherits from the `Agent` class.
   - It has an `act` method that:
     - Generates a unique ID for each interaction.
     - Creates a workspace directory.
     - Uses `FileStore` for file management.
     - Executes the GPTMe chat function.
     - Returns downloaded files from the workspace.
   - Currently lacks advanced memory management features.

2. **Proposed Changes for MemGPT-like Memory Integration:**
   - **Add Memory Structures to the `GPTMe` Class:**
     - Core memory (human and persona sections).
     - Archival memory.
     - Conversation history.
   - **Implement Memory Management Methods:**
     - `core_memory_append`: Appends content to core memory.
     - `archival_memory_insert`: Inserts information into long-term memory.
     - `conversation_search`: Searches through conversation history.
   - **Modify the `act` Method:**
     - Add prompts to conversation history.
     - Pass memory structures to the chat function.
     - Update memories based on the response.
   - **Update `prompts.py`:**
     - Include instructions for new memory features.

3. **Implementation Considerations:**
   - Significant changes required in other parts of the codebase.
   - Need to modify the chat function to handle memory structures.
   - Possible changes to underlying LLM interaction.

**Next Steps:**
- Implement proposed changes in `agents.py`.
- Update `gptme_chat` function to work with new memory structures.
- Modify `prompts.py` to include memory management instructions.
- Test integration of new memory features.
- Update documentation to reflect new capabilities.

**Note:** This plan builds upon the previous MemGPT integration steps, focusing specifically on modifications to the `GPTMe` class and related components.

## 2023-05-13 (Current Date)

### MemGPT-like Memory Management Implementation Plan

1. **Created New File `gptme/memory.py`:**
   - Implemented `GPTMeMemory` class with core memory, archival memory, and conversation history.
   - Added methods for memory management:
     - `core_memory_append`
     - `core_memory_replace`
     - `archival_memory_insert`
     - `archival_memory_search`
     - `conversation_search`

2. **Modified `GPTMe` Class in `gptme/eval/agents.py`:**
   - Integrated `GPTMeMemory` object into the `GPTMe` class.
   - Updated `act` method to pass memory object to `gptme_chat` function.

3. **Updated `gptme_chat` Function in `gptme/__init__.py`:**
   - Added memory-related instructions to the system message.
   - Implemented conversation history tracking.

4. **Updated `prompts.py`:**
   - Added memory management instructions to the `prompt_gptme` function.

**Next Steps:**
- Implement the proposed changes in the respective files.
- Test the integration of new memory features thoroughly.
- Modify other parts of the codebase to utilize the new memory features effectively.
- Update documentation to reflect new memory management capabilities.

**Note:** This implementation provides a basic structure for MemGPT-like memory management in GPTMe. Further development and refinement will be necessary to fully replicate MemGPT's capabilities.

## 2023-05-14 (Current Date)

### Refined MemGPT-like Memory Management Implementation Plan

1. **Create `gptme/memory.py`:**
   - **Implement `GPTMeMemory` Class:**
     - **Purpose:** Manage core memory, archival memory, and conversation history.
     - **Key Components:**
       - **Core Memory:** "human" and "persona" sections (2000 character limit each).
       - **Archival Memory:** Long-term storage for persistent information.
       - **Conversation History:** Tracks past interactions for context-aware responses.

2. **Implement Memory Management Methods in `GPTMeMemory`:**
   - `core_memory_append`: Adds content to a specified core memory section.
     - **Why:** Allows dynamic updating of essential context.
   - `core_memory_replace`: Replaces existing content in a core memory section.
     - **Why:** Enables correction and updating of critical information.
   - `archival_memory_insert`: Stores new information in archival memory.
     - **Why:** Facilitates long-term knowledge retention beyond the context window.
   - `archival_memory_search`: Retrieves information from archival memory based on a query.
     - **Why:** Allows the agent to recall long-term information as needed.
   - `conversation_search`: Searches through conversation history for relevant past interactions.
     - **Why:** Provides context from previous conversations to enhance responses.

3. **Modify `gptme/eval/agents.py`:**
   - **Update `GPTMe` Class to Use `GPTMeMemory`:**
     - **Purpose:** Integrate memory management capabilities directly into the agent.
   - **Integrate Memory Object into the `act` Method:**
     - **Purpose:** Enable the agent to utilize and manage memory during interactions.

4. **Update `gptme/__init__.py`:**
   - **Modify `gptme_chat` Function to Handle Memory Object:**
     - **Add Memory-Related Instructions to System Message:**
       - **Purpose:** Inform the model about available memory management tools.
     - **Implement Conversation History Tracking:**
       - **Purpose:** Keep a log of interactions for context-aware responses.

5. **Update `gptme/prompts.py`:**
   - **Modify `prompt_gptme` Function:**
     - **Include Instructions for Essential Memory Management Features:**
       - **Purpose:** Guide the model on how to use memory management functions.
   - **Update `prompt_tools` Function:**
     - **Describe New Memory Management Capabilities:**
       - **Purpose:** Provide clear descriptions of available memory tools for developers.

6. **Implement LTM State Save/Load Functions:**
   - **Create `save_ltm_state` and `load_ltm_state` Functions:**
     - **Purpose:** Serialize and deserialize the memory state to/from JSON.
   - **Add `save_state` and `load_state` Methods to `GPTMe` Class:**
     - **Purpose:** Enable persistence of memory across sessions.
   - **Determine When and How Often to Save/Load the LTM State:**
     - **Purpose:** Ensure memory integrity and consistency.

7. **Create Unit Tests for New Memory Features:**
   - **Test Each Memory Management Method:**
     - **Purpose:** Verify the correct functioning of individual methods.
   - **Verify Proper Integration with Existing GPTMe Functionality:**
     - **Purpose:** Ensure seamless interaction between memory management and other components.

8. **Update Documentation:**
   - **Add Information About New Memory Management Features to README and Other Relevant Docs:**
     - **Provide Examples of How to Use the New Memory Capabilities:**
       - **Purpose:** Assist developers in understanding and utilizing the new features effectively.

**Next Steps:**
- **Implement Each Step in Order, Testing Thoroughly as You Go:**
  - **Why:** Ensures each component functions correctly before moving to the next.
- **Pay Special Attention to How Memory Management Integrates with Existing GPTMe Functionality:**
  - **Why:** Prevents conflicts and ensures cohesive system behavior.
- **Consider Potential Edge Cases and Error Handling Scenarios:**
  - **Why:** Enhances system robustness and reliability.

## 2023-05-15 (Current Date)

### Refined MemGPT-like Memory Management Implementation Plan

#### Essential Functions (Implement First):

1. **Create `gptme/memory.py`:**
   - **Implement `GPTMeMemory` Class:**
     - **Purpose:** Manage core memory, archival memory, and conversation history.
     - **Key Components:**
       - **Core Memory:** "human" and "persona" sections (2000 character limit each).
       - **Archival Memory:** Long-term storage for persistent information.
       - **Conversation History:** Tracks past interactions for context-aware responses.
   - **Implement Essential Memory Management Methods:**
     - `core_memory_append`: Adds content to a specified core memory section.
       - **Why:** Allows dynamic updating of essential context.
     - `core_memory_replace`: Replaces existing content in a core memory section.
       - **Why:** Enables correction and updating of critical information.
     - `archival_memory_insert`: Stores new information in archival memory.
       - **Why:** Facilitates long-term knowledge retention beyond the context window.
     - `archival_memory_search`: Retrieves information from archival memory based on a query.
       - **Why:** Allows the agent to recall long-term information as needed.
     - `conversation_search`: Searches through conversation history for relevant past interactions.
       - **Why:** Provides context from previous conversations to enhance responses.

2. **Modify `gptme/eval/agents.py`:**
   - **Update `GPTMe` Class to Use `GPTMeMemory`:**
     - **Purpose:** Integrate memory management capabilities directly into the agent.
   - **Integrate Memory Object into the `act` Method:**
     - **Purpose:** Enable the agent to utilize and manage memory during interactions.

3. **Update `gptme/__init__.py`:**
   - **Modify `gptme_chat` Function to Handle Memory Object:**
     - **Add Memory-Related Instructions to System Message:**
       - **Purpose:** Inform the model about available memory management tools.
     - **Implement Basic Conversation History Tracking:**
       - **Purpose:** Keep a log of interactions for context-aware responses.

4. **Update `gptme/prompts.py`:**
   - **Modify `prompt_gptme` Function:**
     - **Include Instructions for Essential Memory Management Features:**
       - **Purpose:** Guide the model on how to use memory management functions.
   - **Update `prompt_tools` Function:**
     - **Describe New Memory Management Capabilities:**
       - **Purpose:** Provide clear descriptions of available memory tools for developers.

5. **Implement Basic LTM State Save/Load Functions:**
   - **Create `save_ltm_state` and `load_ltm_state` Functions:**
     - **Purpose:** Serialize and deserialize the memory state to/from JSON.
   - **Add `save_state` and `load_state` Methods to `GPTMe` Class:**
     - **Purpose:** Enable persistence of memory across sessions.
   - **Determine When and How Often to Save/Load the LTM State:**
     - **Purpose:** Ensure memory integrity and consistency.

#### Functions to Implement Later:

1. **`pause_heartbeats`:**
   - **Related to:** Agent's timing system.
   - **Purpose:** Manage the timing of agent operations.

2. **`conversation_search_date`:**
   - **Related to:** More specific search function for conversation history.
   - **Purpose:** Allows searching conversations based on specific dates.

3. **`schedule_event` and `send_text_message`:**
   - **Related to:** Additional agent capabilities.
   - **Purpose:** Extend the agent's functionality with scheduled actions and messaging.

4. **`send_message`:**
   - **Related to:** User interaction function.
   - **Purpose:** Manage interactions and communications with users.

**Next Steps:**
- **Implement Essential Functions in Order, Testing Thoroughly as You Go:**
  - **Why:** Ensures each component functions correctly before proceeding.
- **Focus on Integrating Core Memory Features with Existing GPTMe Functionality:**
  - **Why:** Prevents conflicts and ensures cohesive system behavior.
- **Once Core Features are Working, Gradually Add Additional Functions to Enhance Capabilities:**
  - **Why:** Builds on a stable foundation, allowing for incremental improvements.
- **Update Documentation and Prompts as New Features are Added:**
  - **Why:** Keeps the project documentation up-to-date and informative.

**Remember:**
- **Consider Error Handling and Edge Cases Throughout the Implementation Process:**
  - **Why:** Enhances system robustness and reliability.

---

## Potentially Relevant Code Snippets from the Current Codebase

```markdown:sidenotes.md
# Project Sidenotes

## 2023-05-10 (Current Date)

### New Session Started

*... [Previous content remains unchanged]...*

## 2023-05-15 (Current Date)

### Refined MemGPT-like Memory Management Implementation Plan

#### Essential Functions (Implement First):

1. **Create `gptme/memory.py`:**
   - **Implement `GPTMeMemory` Class:**
     ```python:path/to/gptme/memory.py
     class GPTMeMemory:
         def __init__(self):
             self.core_memory = {"human": "", "persona": ""}
             self.archival_memory = []
             self.conversation_history = []

         def core_memory_append(self, section: str, content: str) -> None:
             if section in self.core_memory and len(self.core_memory[section]) + len(content) <= 2000:
                 self.core_memory[section] += content
             else:
                 raise ValueError("Section not found or content too long.")

         def core_memory_replace(self, section: str, old_content: str, new_content: str) -> None:
             if section in self.core_memory:
                 self.core_memory[section] = self.core_memory[section].replace(old_content, new_content)
             else:
                 raise ValueError("Section not found.")

         def archival_memory_insert(self, content: str) -> None:
             self.archival_memory.append(content)

         def archival_memory_search(self, query: str) -> Optional[str]:
             for memory in self.archival_memory:
                 if query.lower() in memory.lower():
                     return memory
             return None

         def conversation_search(self, query: str) -> List[str]:
             return [msg for msg in self.conversation_history if query.lower() in msg.lower()]
     ```
     - **Purpose:** This class manages different types of memory essential for the GPTMe agent, allowing for dynamic memory operations and long-term knowledge retention.

2. **Modify `gptme/eval/agents.py`:**
   - **Update `GPTMe` Class to Use `GPTMeMemory`:**
     ```python:path/to/gptme/eval/agents.py
     from gptme.memory import GPTMeMemory

     class GPTMe(Agent):
         def __init__(self, model: str):
             super().__init__(model)
             self.memory = GPTMeMemory()

         def act(self, files: Files | None, prompt: str) -> Files:
             # Existing code...

             # Add to conversation history
             self.memory.conversation_history.append(prompt)

             # Use memory in chat function
             response = gptme_chat(
                 [Message("user", prompt)],
                 [prompt_sys],
                 logdir=log_dir,
                 model=self.model,
                 no_confirm=True,
                 interactive=False,
                 workspace=workspace_dir,
                 memory=self.memory,  # Pass the memory object to gptme_chat
             )

             # Update memories based on response
             # This would require modifying gptme_chat to return structured data

             return store.download()
     ```
     - **Purpose:** Integrates the `GPTMeMemory` class into the `GPTMe` agent, enabling the agent to utilize and manage memory during interactions.

3. **Update `gptme/__init__.py`:**
   - **Modify `gptme_chat` Function to Handle Memory Object:**
     ```python:path/to/gptme/__init__.py
     def gptme_chat(messages, system_messages, logdir, model, no_confirm, interactive, workspace, memory):
         # Existing code...

         # Add memory-related instructions to the system message
         memory_instructions = """
         You have access to the following memory management functions:
         - core_memory_append(section, content)
         - core_memory_replace(section, old_content, new_content)
         - archival_memory_insert(content)
         - archival_memory_search(query)
         - conversation_search(query)
         Use these functions to maintain context and provide more informed responses.
         """
         system_messages[0] = Message(system_messages[0].role, system_messages[0].content + "\n\n" + memory_instructions)

         # Existing code...

         # Inside the chat loop, after processing the AI's response:
         memory.conversation_history.append(ai_message.content)

         # Existing code...
     ```
     - **Purpose:** Enhances the `gptme_chat` function to incorporate memory management by updating system messages and tracking conversation history.

4. **Update `gptme/prompts.py`:**
   - **Modify `prompt_gptme` Function to Include Memory Instructions:**
     ```python:path/to/gptme/prompts.py
     def prompt_gptme(interactive: bool) -> Generator[Message, None, None]:
         base_prompt = f"""
         ... [existing content] ...
         You now have access to advanced memory management tools:
         - Core memory: For essential, foundational context
         - Archival memory: For storing and retrieving larger amounts of information
         - Conversation history: For searching through past interactions
         Use these tools to maintain context and provide more informed responses.

         To save the current state of your long-term memory, use the 'save_state()' method with a specified file path. For example:
         'save_state("path_to_save_ltm_state.json")'

         To load a previously saved state of your long-term memory, use the 'load_state()' method with the path to the saved state file. For example:
         'load_state("path_to_saved_ltm_state.json")'

         These methods will help you persist and restore your memory across different sessions, ensuring continuity and context retention.
         ... [rest of existing content] ...
         """

         interactive_prompt = """
         ... [existing interactive prompt content] ...
         """.strip()

         non_interactive_prompt = """
         ... [existing non-interactive prompt content] ...
         """.strip()

         full_prompt = (
             base_prompt
             + "\n\n"
             + (interactive_prompt if interactive else non_interactive_prompt)
         )
         yield Message("system", full_prompt)
     ```
     - **Purpose:** Updates the system prompt to inform the model about available memory management tools and how to use them effectively.

5. **Implement LTM State Save/Load Functions:**
   - **Create `save_ltm_state` and `load_ltm_state` Functions:**
     ```python:path/to/gptme/memory.py
     import json
     from typing import Dict, List

     def save_ltm_state(core_memory: Dict[str, str], archival_memory: List[str], conversation_history: List[str], file_path: str) -> None:
         ltm_state = {
             'core_memory': core_memory,
             'archival_memory': archival_memory,
             'conversation_history': conversation_history
         }
         with open(file_path, 'w') as file:
             json.dump(ltm_state, file)

     def load_ltm_state(file_path: str) -> Dict[str, List[str]]:
         with open(file_path, 'r') as file:
             ltm_state = json.load(file)
         return ltm_state
     ```
   - **Add `save_state` and `load_state` Methods to `GPTMe` Class:**
     ```python:path/to/gptme/eval/agents.py
     class GPTMe(Agent):
         # ... [existing methods and properties] ...

         def save_state(self, file_path: str) -> None:
             save_ltm_state(self.memory.core_memory, self.memory.archival_memory, self.memory.conversation_history, file_path)

         def load_state(self, file_path: str) -> None:
             ltm_state = load_ltm_state(file_path)
             self.memory.core_memory = ltm_state.get('core_memory', {})
             self.memory.archival_memory = ltm_state.get('archival_memory', [])
             self.memory.conversation_history = ltm_state.get('conversation_history', [])
     ```
     - **Purpose:** Enables the persistence of memory across sessions by saving and loading the long-term memory state.

6. **Create Unit Tests for New Memory Features:**
   - **Test Each Memory Management Method:**
     - **Purpose:** Verify that methods like `core_memory_append` and `archival_memory_search` function correctly.
   - **Verify Proper Integration with Existing GPTMe Functionality:**
     - **Purpose:** Ensure that integrating memory management does not disrupt existing features.

7. **Update Documentation:**
   - **Add Information About New Memory Management Features to README and Other Relevant Docs:**
     - **Provide Examples of How to Use the New Memory Capabilities:**
       - **Purpose:** Assist developers in understanding and utilizing the new features effectively.

#### Functions to Implement Later:

1. **`pause_heartbeats`:**
   - **Related to:** Agent's timing system.
   - **Purpose:** Manage the timing of agent operations, such as pausing periodic tasks.

2. **`conversation_search_date`:**
   - **Related to:** More specific search function for conversation history.
   - **Purpose:** Allows searching conversations based on specific dates, enhancing historical context retrieval.

3. **`schedule_event` and `send_text_message`:**
   - **Related to:** Additional agent capabilities.
   - **Purpose:** Extend the agent's functionality with scheduled actions and messaging capabilities.

4. **`send_message`:**
   - **Related to:** User interaction function.
   - **Purpose:** Manage interactions and communications with users, enabling real-time messaging features.

**Next Steps:**
- **Implement Essential Functions in Order, Testing Thoroughly as You Go:**
  - **Why:** Ensures each component functions correctly before proceeding to the next step.
- **Focus on Integrating Core Memory Features with Existing GPTMe Functionality:**
  - **Why:** Prevents conflicts and ensures cohesive system behavior.
- **Once Core Features are Working, Gradually Add Additional Functions to Enhance Capabilities:**
  - **Why:** Builds on a stable foundation, allowing for incremental improvements.
- **Update Documentation and Prompts as New Features are Added:**
  - **Why:** Keeps the project documentation up-to-date and informative.

**Remember:**
- **Consider Error Handling and Edge Cases Throughout the Implementation Process:**
  - **Why:** Enhances system robustness and reliability.

---

## Additional Integration Insights

### Understanding MemGPT Memory Management

Based on the provided Letta aka MemGPT documentation, the integration of MemGPT-like memory management into GPTMe involves several key concepts and components:

1. **In-Context Memory:**
   - Reserved section of the LLM context window editable by the agent.
   - Extends the `BaseMemory` class, allowing dynamic memory management.
   - **Components:**
     - **Memory Sections:** E.g., “human”, “persona”, and customizable sections like “organization”.
     - **Memory Editing Functions:** `core_memory_replace` and `core_memory_append`.

2. **External Memory:**
   - **Archival Memory:** Stored in a vector database for long-term information retention.
     - Tools: `archival_memory_search`, `archival_memory_insert`.
   - **Recall Memory:** Logs all conversational history.
     - Tools: `conversation_search`, `conversation_search_date`.

3. **Custom Memory Modules:**
   - Extend `BaseMemory` and `ChatMemory` to implement custom memory sections and management functions.
   - Example: `TaskMemory` class that manages a task queue alongside existing memory sections.

4. **Memory Management Tools:**
   - Agents are provided with tools to interact with both in-context and external memory.
   - **Default Tools:**
     - **Core Memory Tools:** `core_memory_append`, `core_memory_replace`.
     - **Archival Memory Tools:** `archival_memory_insert`, `archival_memory_search`.
     - **Recall Memory Tools:** `conversation_search`, `conversation_search_date`.

5. **Persistence and Statefulness:**
   - Implement mechanisms to save and load memory states, ensuring persistence across sessions.
   - Essential for maintaining continuity and context in agent interactions.

6. **Memory as a Task Queue (Custom Implementation Example):**
   - **TaskMemory Class:**
     - Adds a “tasks” section to manage a queue of tasks.
     - Methods: `task_queue_push`, `task_queue_pop`.
     - **Usage:** Keeps track of tasks the agent must accomplish, ensuring they are completed sequentially.

### Implementation Insights

- **Why Implement Each Step:**
  - **Memory Structure:** Provides a foundational framework for managing different types of memory, enabling context-aware interactions.
  - **Memory Management Functions:** Facilitates the manipulation and retrieval of memory, allowing the agent to update and access information as needed.
  - **Prompts Modification:** Ensures the model is aware of memory management capabilities, guiding its usage during interactions.
  - **Integration with Existing Structure:** Seamlessly incorporates memory features into the agent’s workflow, enhancing its functionality without disrupting existing operations.
  - **Save/Load Functions:** Provides persistence, crucial for maintaining statefulness and continuity across interactions.
  - **Testing and Documentation:** Ensures reliability, usability, and maintainability of the new memory features.

- **Developer Understanding:**
  - Each function and component is designed to enhance the agent’s ability to manage and utilize memory effectively.
  - Clear separation of core, archival, and conversation memory ensures organized and efficient memory handling.
  - Providing memory management tools empowers the agent to self-manage its context, improving response accuracy and relevance.

**Example of Custom Memory Module Implementation:**

```python:path/to/gptme/memory.py
from letta.memory import ChatMemory, MemoryModule
from typing import Optional, List

class TaskMemory(ChatMemory): 

    def __init__(self, human: str, persona: str, tasks: List[str]): 
        super().__init__(human=human, persona=persona) 
        self.memory["tasks"] = MemoryModule(limit=2000, value=tasks)  # Create an empty task list 

    def task_queue_push(self, task_description: str) -> Optional[str]:
        """
        Push to a task queue stored in core memory. 

        Args:
            task_description (str): A description of the next task you must accomplish. 
            
        Returns:
            Optional[str]: None is always returned as this function does not produce a response.
        """
        self.memory["tasks"].value.append(task_description)
        return None

    def task_queue_pop(self) -> Optional[str]:
        """
        Get the next task from the task queue 

        Returns:
            Optional[str]: The description of the task popped from the queue, 
            if there are still tasks in queue. Otherwise, returns None (the 
            task queue is empty)
        """
        if len(self.memory["tasks"].value) == 0: 
            return None
        task = self.memory["tasks"].value[0]
        self.memory["tasks"].value = self.memory["tasks"].value[1:]
        return task
```

- **Purpose:** Extends `ChatMemory` to include a task queue, allowing the agent to manage and prioritize tasks effectively.

**Creating an Agent with Custom Memory:**

```python:path/to/agent_creation.py
task_agent_state = client.create_agent(
    name="task_agent", 
    memory=TaskMemory(
    human="My name is Sarah",
        persona="You have an additional section of core memory called `tasks`. " \
        + "This section of memory contains a list of tasks you must do." \
        + "Use the `task_queue_push` tool to write down tasks so you don't forget to do them." \
        + "If there are tasks in the task queue, you should call `task_queue_pop` to retrieve and remove them. " \
        + "Keep calling `task_queue_pop` until there are no more tasks in the queue. " \
        + "Do *not* call `send_message` until you have completed all tasks in your queue. " \
        + "If you call `task_queue_pop`, you must always do what the popped task specifies", 
        tasks=["start calling yourself Bob", "tell me a haiku with my name"], 
    )
)
```

- **Purpose:** Creates an agent with a customized memory structure that includes a task queue, enhancing task management capabilities.

---

**Final Note:**
This comprehensive implementation plan, combined with the insights from the MemGPT documentation, equips developers with a clear roadmap to integrate advanced memory management features into GPTMe. By following these steps meticulously, the GPTMe agent will achieve enhanced context-awareness and memory persistence, significantly improving its interaction capabilities.
