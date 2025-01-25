import logging
from abc import abstractmethod
import os

from gptme import Message
from gptme import chat as gptme_chat
from gptme import get_prompt
from gptme.cli import get_name
from gptme.config import get_config
from gptme.tools import init_tools

from ..tools import ToolFormat
from .filestore import FileStore
from .types import Files

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, model: str, tool_format: ToolFormat = "markdown"):
        self.model = model
        self.tool_format = tool_format

    @abstractmethod
    def act(self, files: Files | None, prompt: str) -> Files:
        """
        Carries out the prompt and returns artifacts in the form of `Files`.
        """
        raise NotImplementedError


class GPTMe(Agent):
    def act(self, files: Files | None, prompt: str):
        _id = abs(hash(prompt)) % 1000000
        model_fmt = f"{self.model.replace('/', '--')}-{self.tool_format}"
        name = get_name(f"gptme-evals-{model_fmt}-{_id}")

        os.environ["SESSION_NAME"] = name
        os.environ["TOOL_FORMAT"] = self.tool_format
        os.environ["WORKSPACE"] = "@log"

        config = get_config()

        store = FileStore(working_dir=config.get_workspace_dir())

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
        try:
            gptme_chat(
                [Message("user", prompt)],
                [prompt_sys],
                model=self.model,
                no_confirm=True,
                interactive=False,
            )
        # don't exit on sys.exit()
        except (SystemExit, KeyboardInterrupt):
            pass
        print("--- Finished generation ---\n")

        return store.download()
