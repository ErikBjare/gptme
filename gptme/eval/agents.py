import logging
from abc import abstractmethod

from gptme import Message
from gptme import chat as gptme_chat
from gptme import get_prompt
from gptme.cli import get_name
from gptme.dirs import get_logs_dir
from gptme.tools import init_tools
from gptme.letta_integration import create_letta_agent

from .filestore import FileStore
from .types import Files

logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    def act(self, files: Files | None, prompt: str) -> Files:
        """
        Carries out the prompt and returns artifacts in the form of `Files`.
        """
        raise NotImplementedError

class GPTMe(Agent):
    def act(self, files: Files | None, prompt: str):
        _id = abs(hash(prompt)) % 1000000
        name = get_name(f"gptme-evals-{self.model.replace('/', '--')}-{_id}")
        log_dir = get_logs_dir() / name
        workspace_dir = log_dir / "workspace"
        if workspace_dir.exists():
            raise FileExistsError(
                f"Workspace directory {workspace_dir} already exists."
            )

        store = FileStore(working_dir=workspace_dir)
        if files:
            store.upload(files)

        # TODO: make eval toolset configurable
        init_tools()

        print("\n--- Start of generation ---")
        logger.debug(f"Working in {store.working_dir}")
        prompt_sys = get_prompt()
        prompt_sys = prompt_sys.replace(
            content=prompt_sys.content
            + "\n\nIf you have trouble and dont seem to make progress, stop trying."
        )
        
        letta_agent = create_letta_agent()
        
        try:
            # Retrieve archival memory
            archival_memory = letta_agent.get_archival_memory()
            
            # Prepare the prompt with archival memory
            memory_prompt = "Relevant information from previous interactions:\n"
            memory_prompt += "\n".join(archival_memory[-5:])  # Include last 5 memories
            full_prompt = f"{memory_prompt}\n\nUser: {prompt}"
            
            response = gptme_chat(
                [Message("user", full_prompt)],
                [prompt_sys],
                logdir=log_dir,
                model=self.model,
                no_confirm=True,
                interactive=False,
                workspace=workspace_dir,
                letta_agent=letta_agent,
            )
            
            # Extract and store new information in archival memory
            new_info = extract_new_info(response)  # Implement this function
            letta_agent.insert_archival_memory(new_info)
            
        # don't exit on sys.exit()
        except (SystemExit, KeyboardInterrupt):
            pass
        print("--- Finished generation ---\n")

        return store.download()
