import errno
import importlib.metadata
import io
import logging
import os
import re
import readline  # noqa: F401
import sys
import urllib.parse
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Literal

import click
from pick import pick
from rich import print  # noqa: F401
from rich.console import Console

from .commands import CMDFIX, action_descriptions, execute_cmd
from .config import get_workspace_prompt
from .constants import MULTIPROMPT_SEPARATOR, PROMPT_USER
from .dirs import get_logs_dir
from .init import init, init_logging
from .llm import reply
from .logmanager import LogManager, _conversations
from .message import Message
from .models import get_model
from .prompts import get_prompt
from .tools import execute_msg, get_tool
from .tools.browser import read_url
from .util import epoch_to_age, generate_name

logger = logging.getLogger(__name__)
print_builtin = __builtins__["print"]  # type: ignore

# TODO: these are a bit redundant/incorrect
LLMChoice = Literal["openai", "anthropic", "local"]
ModelChoice = Literal["gpt-3.5-turbo", "gpt-4", "gpt-4-1106-preview"]


script_path = Path(os.path.realpath(__file__))
action_readme = "\n".join(
    f"  {CMDFIX}{cmd:11s}  {desc}." for cmd, desc in action_descriptions.items()
)


docstring = f"""
GPTMe, a chat-CLI for LLMs, enabling them to execute commands and code.

If PROMPTS are provided, a new conversation will be started with it.

If one of the PROMPTS is '{MULTIPROMPT_SEPARATOR}', following prompts will run after the assistant is done answering the first one.

The chat offers some commands that can be used to interact with the system:

\b
{action_readme}"""


@click.command(help=docstring)
@click.argument(
    "prompts",
    default=None,
    required=False,
    nargs=-1,
)
@click.option(
    "--prompt-system",
    default="full",
    help="System prompt. Can be 'full', 'short', or something custom.",
)
@click.option(
    "--name",
    default="random",
    help="Name of conversation. Defaults to generating a random name. Pass 'ask' to be prompted for a name.",
)
@click.option(
    "--model",
    default=None,
    help="Model to use, e.g. openai/gpt-4-turbo, anthropic/claude-3-5-sonnet-20240620. If only provider is given, the default model for that provider is used.",
)
@click.option(
    "--stream/--no-stream",
    is_flag=True,
    default=True,
    help="Stream responses",
)
@click.option("-v", "--verbose", is_flag=True, help="Verbose output.")
@click.option(
    "-y", "--no-confirm", is_flag=True, help="Skips all confirmation prompts."
)
@click.option(
    "--interactive/--non-interactive",
    "-i/-n",
    default=True,
    help="Choose interactive mode, or not. Non-interactive implies --no-confirm, and is used in testing.",
)
@click.option(
    "--show-hidden",
    is_flag=True,
    help="Show hidden system messages.",
)
@click.option(
    "-r",
    "--resume",
    is_flag=True,
    help="Load last conversation",
)
@click.option(
    "--version",
    is_flag=True,
    help="Show version and configuration information",
)
@click.option(
    "--workspace",
    help="Path to workspace directory. Pass '@log' to create a workspace in the log directory.",
    default=".",
)
def main(
    prompts: list[str],
    prompt_system: str,
    name: str,
    model: ModelChoice,
    stream: bool,
    verbose: bool,
    no_confirm: bool,
    interactive: bool,
    show_hidden: bool,
    version: bool,
    resume: bool,
    workspace: str,
):
    """Main entrypoint for the CLI."""
    if version:
        # print version
        print_builtin(f"gptme {importlib.metadata.version('gptme-python')}")

        # print dirs
        print_builtin(f"Logs dir: {get_logs_dir()}")

        exit(0)

    if "PYTEST_CURRENT_TEST" in os.environ:
        interactive = False

    # init logging
    init_logging(verbose)

    if not interactive:
        no_confirm = True

    if no_confirm:
        logger.warning("Skipping all confirmation prompts.")

    # get initial system prompt
    initial_msgs = [get_prompt(prompt_system)]

    # if stdin is not a tty, we're getting piped input, which we should include in the prompt
    if not sys.stdin.isatty():
        # fetch prompt from stdin
        prompt_stdin = _read_stdin()
        if prompt_stdin:
            initial_msgs += [Message("system", f"```stdin\n{prompt_stdin}\n```")]

            # Attempt to switch to interactive mode
            sys.stdin.close()
            try:
                sys.stdin = open("/dev/tty")
            except OSError:
                # if we can't open /dev/tty, we're probably in a CI environment, so we should just continue
                logger.warning(
                    "Failed to switch to interactive mode, continuing in non-interactive mode"
                )

    # if resume
    if resume:
        name = "resume"  # magic string to load last conversation

    # join prompts, grouped by `-` if present, since that's the separator for multiple-round prompts
    sep = "\n\n" + MULTIPROMPT_SEPARATOR
    prompts = [p.strip() for p in "\n\n".join(prompts).split(sep) if p]
    prompt_msgs = [Message("user", p) for p in prompts]

    chat(
        prompt_msgs,
        initial_msgs,
        name,
        model,
        stream,
        no_confirm,
        interactive,
        show_hidden,
        workspace,
    )


def chat(
    prompt_msgs: list[Message],
    initial_msgs: list[Message],
    name: str,
    model: str | None,
    stream: bool = True,
    no_confirm: bool = False,
    interactive: bool = True,
    show_hidden: bool = False,
    workspace: str = ".",
):
    """
    Run the chat loop.

    prompt_msgs: list of messages to execute in sequence.
    initial_msgs: list of history messages.
    workspace: path to workspace directory, or @log to create one in the log directory.

    Callable from other modules.
    """
    # init
    init(model, interactive)

    # we need to run this before checking stdin, since the interactive doesn't work with the switch back to interactive mode
    logfile = get_logfile(
        name, interactive=(not prompt_msgs and interactive) and sys.stdin.isatty()
    )
    print(f"Using logdir {logfile.parent}")
    log = LogManager.load(logfile, initial_msgs=initial_msgs, show_hidden=show_hidden)

    # change to workspace directory
    # use if exists, create if @log, or use given path
    if (logfile.parent / "workspace").exists():
        assert workspace in ["@log", "."], "Workspace already exists"
        workspace_path = logfile.parent / "workspace"
        print(f"Using workspace at {workspace_path}")
    elif workspace == "@log":
        workspace_path = logfile.parent / "workspace"
        print(f"Creating workspace at {workspace_path}")
        os.makedirs(workspace_path, exist_ok=True)
    else:
        workspace_path = Path(workspace)
        assert (
            workspace_path.exists()
        ), f"Workspace path {workspace_path} does not exist"
    os.chdir(workspace_path)

    # check if workspace already exists
    workspace_prompt = get_workspace_prompt(str(workspace_path))
    if workspace_prompt:
        log.append(Message("system", workspace_prompt, hide=True))

    # print log
    log.print()
    print("--- ^^^ past messages ^^^ ---")

    # main loop
    while True:
        # if prompt_msgs given, insert next prompt into log
        if prompt_msgs:
            msg = prompt_msgs.pop(0)
            msg = _include_paths(msg)
            log.append(msg)
            # if prompt is a user-command, execute it
            if execute_cmd(msg, log):
                continue
        # if:
        #  - prompts exhausted
        #  - non-interactive
        #  - no executable block in last assistant message
        # then exit
        elif not interactive:
            # noreorder
            from .tools import is_supported_codeblock_tool  # fmt: skip

            # continue if we can run tools on the last message
            runnable = False
            if codeblock := log.get_last_code_block("assistant", history=1):
                lang, _ = codeblock
                if is_supported_codeblock_tool(lang):
                    runnable = True
            if not runnable:
                logger.info("Non-interactive and exhausted prompts, exiting")
                break

        # ask for input if no prompt, generate reply, and run tools
        for msg in step(log, no_confirm, stream=stream):  # pragma: no cover
            log.append(msg)
            # run any user-commands, if msg is from user
            if msg.role == "user" and execute_cmd(msg, log):
                break


def step(
    log: LogManager,
    no_confirm: bool,
    stream: bool = True,
) -> Generator[Message, None, None]:
    """Runs a single pass of the chat."""

    # if last message was from assistant, try to run tools again
    # FIXME: can't do this here because it will run twice
    # if log[-1].role == "assistant":
    #     yield from execute_msg(log[-1], ask=not no_confirm)

    # If last message was a response, ask for input.
    # If last message was from the user (such as from crash/edited log),
    # then skip asking for input and generate response
    last_msg = log[-1] if log else None
    if (
        not last_msg
        or (last_msg.role in ["assistant"])
        or last_msg.content == "Interrupted"
        or last_msg.pinned
    ):  # pragma: no cover
        inquiry = prompt_user()
        if not inquiry:
            # Empty command, ask for input again
            print()
            return
        msg = Message("user", inquiry, quiet=True)
        msg = _include_paths(msg)
        yield msg

    # print response
    try:
        # performs reduction/context trimming, if necessary
        msgs = log.prepare_messages()

        for m in msgs:
            logger.debug(f"Prepared message: {m}")

        # generate response
        msg_response = reply(msgs, get_model().model, stream)

        # log response and run tools
        if msg_response:
            msg_response.quiet = True
            yield msg_response
            yield from execute_msg(msg_response, ask=not no_confirm)
    except KeyboardInterrupt:
        yield Message("system", "Interrupted")


def get_name(name: str) -> Path:
    """
    Returns a name for the new conversation.

    If name is "random", generates a random name.
    If name is "ask", asks the user for a name.
    If name is starts with a date, uses it as is.
    Otherwise, prepends the current date to the name.
    """
    datestr = datetime.now().strftime("%Y-%m-%d")
    logsdir = get_logs_dir()

    # returns a name for the new conversation
    if name == "random":
        # check if name exists, if so, generate another one
        for _ in range(3):
            name = generate_name()
            logpath = logsdir / f"{datestr}-{name}"
            if not logpath.exists():
                break
        else:
            raise ValueError("Failed to generate unique name")
    elif name == "ask":  # pragma: no cover
        while True:
            # ask for name, or use random name
            name = input("Name for conversation (or empty for random words): ")
            name = f"{datestr}-{name}"
            logpath = logsdir / name

            # check that name is unique/doesn't exist
            if not logpath.exists():
                break
            else:
                print(f"Name {name} already exists, try again.")
    else:
        # if name starts with date, use as is
        try:
            datetime.strptime(name[:10], "%Y-%m-%d")
        except ValueError:
            name = f"{datestr}-{name}"
        logpath = logsdir / name
    return logpath


def get_logfile(name: str | Literal["random", "resume"], interactive=True) -> Path:
    # let user select between starting a new conversation and loading a previous one
    # using the library
    title = "New conversation or load previous? "
    NEW_CONV = "New conversation"
    prev_conv_files = list(reversed(_conversations()))

    if name == "resume":
        if prev_conv_files:
            return prev_conv_files[0].parent / "conversation.jsonl"
        else:
            raise ValueError("No previous conversations to resume")

    # filter out test conversations
    # TODO: save test convos to different folder instead
    # def is_test(name: str) -> bool:
    #     return "-test-" in name or name.startswith("test-")
    # prev_conv_files = [f for f in prev_conv_files if not is_test(f.parent.name)]

    NEWLINE = "\n"
    prev_convs = [
        f"{f.parent.name:30s} \t{epoch_to_age(f.stat().st_mtime)} \t{len(f.read_text().split(NEWLINE)):5d} msgs"
        for f in prev_conv_files
    ]

    # don't run pick in tests/non-interactive mode, or if the user specifies a name
    if interactive and name not in ["random", "ask"]:
        options = [
            NEW_CONV,
        ] + prev_convs

        index: int
        _, index = pick(options, title)  # type: ignore
        if index == 0:
            logdir = get_name(name)
        else:
            logdir = get_logs_dir() / prev_conv_files[index - 1].parent
    else:
        logdir = get_name(name)

    if not os.path.exists(logdir):
        os.mkdir(logdir)
    logfile = logdir / "conversation.jsonl"
    if not os.path.exists(logfile):
        open(logfile, "w").close()
    return logfile


def prompt_user(value=None) -> str:  # pragma: no cover
    response = prompt_input(PROMPT_USER, value)
    if response:
        readline.add_history(response)
    return response


def prompt_input(prompt: str, value=None) -> str:  # pragma: no cover
    prompt = prompt.strip() + ": "
    if value:
        print(prompt + value)
    else:
        prompt = _rich_to_str(prompt)

        # https://stackoverflow.com/a/53260487/965332
        original_stdout = sys.stdout
        sys.stdout = sys.__stdout__
        value = input(prompt.strip() + " ")
        sys.stdout = original_stdout
    return value


def _rich_to_str(s: str) -> str:
    console = Console(file=io.StringIO(), color_system="256")
    console.print(s)
    return console.file.getvalue()  # type: ignore


def _read_stdin() -> str:
    chunk_size = 1024  # 1 KB
    all_data = ""

    while True:
        chunk = sys.stdin.read(chunk_size)
        if not chunk:
            break
        all_data += chunk

    return all_data


def _include_paths(msg: Message) -> Message:
    """
    Searches the message for any valid paths and:
     - appends the contents of such files as codeblocks.
     - include images as files.
    """
    # TODO: add support for directories?
    assert msg.role == "user"

    # list the current directory
    cwd_files = [f.name for f in Path.cwd().iterdir()]

    # match absolute, home, relative paths, and URLs anywhere in the message
    # could be wrapped with spaces or backticks, possibly followed by a question mark
    # don't look in codeblocks, and don't match paths that are already in codeblocks
    # TODO: this will misbehave if there are codeblocks (or triple backticks) in codeblocks
    content_no_codeblocks = re.sub(r"```.*?\n```", "", msg.content, flags=re.DOTALL)
    append_msg = ""
    for word in re.split(r"[\s`]", content_no_codeblocks):
        # remove wrapping backticks
        word = word.strip("`")
        # remove trailing question mark
        word = word.rstrip("?")
        if not word:
            continue
        if (
            # if word starts with a path character
            any(word.startswith(s) for s in ["/", "~/", "./"])
            # or word is a URL
            or word.startswith("http")
            # or word is a file in the current dir,
            # or a path that starts in a folder in the current dir
            or any(word.split("/", 1)[0] == file for file in cwd_files)
        ):
            logger.debug(f"potential path/url: {word=}")
            contents = _parse_prompt(word)
            if contents:
                # if we found a valid path, replace it with the contents of the file
                append_msg += "\n\n" + contents

            file = _parse_prompt_files(word)
            if file:
                msg.files.append(file)

    # append the message with the file contents
    if append_msg:
        msg.content += append_msg

    return msg


def _parse_prompt(prompt: str) -> str | None:
    """
    Takes a string that might be a path,
    and if so, returns the contents of that file wrapped in a codeblock.
    """
    # if prompt is a command, exit early (as commands might take paths as arguments)
    if any(
        prompt.startswith(command)
        for command in [f"{CMDFIX}{cmd}" for cmd in action_descriptions.keys()]
    ):
        return None

    try:
        # check if prompt is a path, if so, replace it with the contents of that file
        f = Path(prompt).expanduser()
        if f.exists() and f.is_file():
            return f"```{prompt}\n{Path(prompt).expanduser().read_text()}\n```"
    except OSError as oserr:
        # some prompts are too long to be a path, so we can't read them
        if oserr.errno != errno.ENAMETOOLONG:
            pass
        raise
    except UnicodeDecodeError:
        # some files are not text files (images, audio, PDFs, binaries, etc), so we can't read them
        # TODO: but can we handle them better than just printing the path? maybe with metadata from `file`?
        # logger.warning(f"Failed to read file {prompt}: not a text file")
        return None

    # check if any word in prompt is a path or URL,
    # if so, append the contents as a code block
    words = prompt.split()
    paths = []
    urls = []
    for word in words:
        f = Path(word).expanduser()
        if f.exists() and f.is_file():
            paths.append(word)
            continue
        try:
            p = urllib.parse.urlparse(word)
            if p.scheme and p.netloc:
                urls.append(word)
        except ValueError:
            pass

    result = ""
    if paths or urls:
        result += "\n\n"
        if paths:
            logger.debug(f"{paths=}")
        if urls:
            logger.debug(f"{urls=}")
    for path in paths:
        result += _parse_prompt(path) or ""

    if get_tool("browser") is None:
        logger.warning("Browser tool not available, skipping URL read")
    else:
        for url in urls:
            try:
                content = read_url(url)
                result += f"```{url}\n{content}\n```"
            except Exception as e:
                logger.warning(f"Failed to read URL {url}: {e}")

    return result


def _parse_prompt_files(prompt: str) -> Path | None:
    """
    Takes a string that might be a image path or PDF, to be attached to the message, and returns the path.
    """
    allowed_exts = ["png", "jpg", "jpeg", "gif", "pdf"]

    # if prompt is a command, exit early (as commands might take paths as arguments)
    if any(
        prompt.startswith(command)
        for command in [f"{CMDFIX}{cmd}" for cmd in action_descriptions.keys()]
    ):
        return None

    try:
        # check if prompt is a path, if so, replace it with the contents of that file
        p = Path(prompt)
        if p.exists() and p.is_file() and p.suffix[1:] in allowed_exts:
            logger.warning("Attaching file to message")
            return p
        else:
            return None
    except OSError as oserr:
        # some prompts are too long to be a path, so we can't read them
        if oserr.errno != errno.ENAMETOOLONG:
            return None
        raise


if __name__ == "__main__":
    main()
