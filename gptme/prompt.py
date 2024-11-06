import logging
from collections.abc import Callable

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.formatted_text import ANSI, HTML, to_formatted_text
from prompt_toolkit.history import FileHistory

from .commands import COMMANDS
from .dirs import get_pt_history_file

logger = logging.getLogger(__name__)


class GptmeCompleter(Completer):
    """Completer that combines command, path and LLM suggestions."""

    def __init__(self, llm_suggest_callback: Callable[[str], list[str]] | None = None):
        self.path_completer = PathCompleter()
        self.llm_suggest_callback = llm_suggest_callback

    def get_completions(self, document, complete_event):
        document.get_word_before_cursor()
        text = document.text_before_cursor

        # Command completion
        if text.startswith("/"):
            cmd_text = text[1:]
            for cmd in COMMANDS:
                if cmd.startswith(cmd_text):
                    yield Completion(
                        cmd,
                        start_position=-len(cmd_text),
                        display=HTML(f"<blue>/{cmd}</blue>"),
                    )

        # Path completion
        elif any(text.startswith(prefix) for prefix in ["../", "~/", "./"]):
            yield from self.path_completer.get_completions(document, complete_event)

        # LLM suggestions
        elif self.llm_suggest_callback and len(text) > 2:
            try:
                suggestions = self.llm_suggest_callback(text)
                if suggestions:
                    for suggestion in suggestions:
                        if suggestion.startswith(text):
                            yield Completion(
                                suggestion,
                                start_position=-len(text),
                                display_meta="AI suggestion",
                            )
            except Exception:
                # Fail silently if LLM suggestions timeout/fail
                pass


def create_prompt_session(
    llm_suggest_callback: Callable[[str], list[str]] | None = None,
) -> PromptSession:
    """Create a PromptSession with history and completion support."""
    history = FileHistory(str(get_pt_history_file()))
    completer = GptmeCompleter(llm_suggest_callback)

    return PromptSession(
        history=history,
        completer=completer,
        complete_while_typing=True,
        enable_history_search=True,
    )


def get_input(
    prompt: str = "Human: ",
    llm_suggest_callback: Callable[[str], list[str]] | None = None,
) -> str:
    """Get input from user with completion support."""
    session = create_prompt_session(llm_suggest_callback)
    try:
        logger.debug(f"Original prompt: {repr(prompt)}")

        # https://stackoverflow.com/a/53260487/965332
        # original_stdout = sys.stdout
        # sys.stdout = sys.__stdout__
        # value = input(prompt.strip() + " ")
        result = session.prompt(to_formatted_text(ANSI(prompt.rstrip() + " ")))
        # sys.stdout = original_stdout
        return result
    except (EOFError, KeyboardInterrupt) as e:
        # Re-raise EOFError to handle Ctrl+D properly
        if isinstance(e, EOFError):
            raise
        return ""


def add_history(line: str) -> None:
    """Add a line to the prompt_toolkit history."""
    session = create_prompt_session()
    session.history.append_string(line)
