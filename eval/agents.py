import os
from abc import abstractmethod

from gptme import Message
from gptme import chat as gptme_chat
from gptme import get_prompt

from .filestore import FileStore
from .types import Files


class Agent:
    @abstractmethod
    def act(self, files: Files | None, prompt: str) -> Files:
        """
        Carries out the prompt and returns artifacts in the form of `Files`.
        """
        raise NotImplementedError


class GPTMe(Agent):
    def act(self, files: Files | None, prompt: str):
        store = FileStore()
        os.chdir(store.working_dir)  # can now modify store content

        if files:
            store.upload(files)

        print("\n--- Start of generation ---")
        print(f"Working in {store.working_dir}")
        # TODO: add timeout
        try:
            gptme_chat(
                [Message("user", prompt)],
                [get_prompt()],
                f"gptme-evals-{store.id}",
                llm=None,
                model=None,
                no_confirm=True,
                interactive=False,
            )
        # don't exit on sys.exit()
        except (SystemExit, KeyboardInterrupt):
            pass
        print("--- Finished generation ---\n")

        return store.download()
