import os
from abc import abstractmethod

from gptme import Message
from gptme import chat as gptme_chat
from gptme import get_prompt

from .filestore import FileStore
from .types import Files


class Agent:
    def __init__(self, llm: str, model: str):
        self.llm = llm
        self.model = model

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
        prompt_sys = get_prompt()
        prompt_sys.content += (
            "\n\nIf you have trouble and dont seem to make progress, stop trying."
        )
        # TODO: add timeout
        try:
            gptme_chat(
                [Message("user", prompt)],
                [prompt_sys],
                f"gptme-evals-{store.id}",
                llm=self.llm,
                model=self.model,
                no_confirm=True,
                interactive=False,
            )
        # don't exit on sys.exit()
        except (SystemExit, KeyboardInterrupt):
            pass
        print("--- Finished generation ---\n")

        return store.download()
