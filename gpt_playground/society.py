"""
This is a long-living agent that is designed to be a companion to the user.

It should be able to help the user in various ways, such as:

 - Acting as an executive assistant
 - Answering questions
 - Helping strategize
 - Giving advice
 - Writing code
 - Writing prose (such as email, code docs, etc.)
 - Providing companionship

The agent should be able to learn from the user and adapt to their needs.

Since the agent is long-living, it should be able to remember things that the user has told it,
to do so, it needs to be able to store and query past conversations in a database.

If the AI gives a bad response, the user should be able to correct it.
"""
from typing import Literal, Generator
from datetime import datetime
import logging
import json
import os
import shutil
import textwrap
from termcolor import colored, cprint
from joblib import Memory

import openai

memory = Memory(".cache/", verbose=0)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

USER = os.environ["USER"]
ABOUT_USER = """
Erik Bjäreholt is a software engineer who is passionate about building tools that make people's lives easier.
He is known for building ActivityWatch, a open-source time tracking app.
"""

EMOJI_WARN = "⚠️"


class Message:
    """A message sent to or from the AI."""
    def __init__(self, role: Literal['system', 'user', 'assistant'], content: str, user: str = None):
        assert role in ["system", "user", "assistant"]
        self.role = role
        self.content = content
        if user:
            self.user = user
        else:
            self.user = {"system": "System", "user": "User", "assistant": "Assistant"}[role]
        self.timestamp = datetime.now()

    def to_dict(self):
        """Return a dict representation of the message, serializable to JSON."""
        return {
            "role": self.role,
            "content": self.content,
        }


def get_logfile() -> str:
    logdir = "logs/"
    if not os.path.exists(logdir):
        os.mkdir(logdir)
    logfile = logdir + datetime.now().strftime("%Y-%m-%d") + ".log"
    if not os.path.exists(logfile):
        open(logfile, "w").close()
    return logfile


def initial_prompt() -> list[Message]:
    """Initial prompt to start the conversation. If no history given."""
    msgs = []
    msgs.append(Message("system", __doc__))
    msgs.append(Message("system", "The name of the user is " + USER))
    msgs.append(Message("system", "Here is some information about the user: " + ABOUT_USER))
    msgs.append(Message("system", "The assistant can use the following tools:" + """
- Terminal
    - Use it by writing a markdown code block starting with ```bash
    - Or, use it with "terminal: <shell code>"
    - Do not preceed commands with a dollar sign
- Python interpreter
    - Use it by writing a markdown code block starting with ```python
    - Or, use it with ">>> <python code>"
- Save and load files
    - Saving can be done by writing "save: <filename>" on the line after a code block
    - Loading can be done by writing "load: <filename>"
    - Save example: ```python
print("Hello world!")
```
save: hello.py
    - Load example:
load: hello.py


To use a tool, the response must contain the command exactly as written above, without quotes or preamble.
    """))
    msgs.append(Message("assistant", "Hello, I am your personal AI assistant. How may I help you today?"))
    return msgs


def read_log() -> list[Message]:
    """Reads the conversation log."""
    logfile = get_logfile()
    with open(logfile, "r") as file:
        log = [Message(**json.loads(line)) for line in file.readlines()]
    if not log:
        log = initial_prompt()
    return log


def write_log(msg_or_log: Message | list[Message]) -> None:
    """
    Writes to the conversation log.
    If a single message given, append.
    If a list of messages given, overwrite.
    """
    logfile = get_logfile()
    if isinstance(msg_or_log, Message):
        msg = msg_or_log
        with open(logfile, "a") as file:
            file.write(json.dumps(msg.to_dict()) + "\n")
    elif isinstance(msg_or_log, list):
        log = msg_or_log
        with open(logfile, "w") as file:
            for msg in log:
                file.write(json.dumps(msg.to_dict()) + "\n")
    else:
        raise TypeError("Expected Message or list of Messages, got " + str(type(msg_or_log)))


def msgs2text(msgs: list[Message]) -> str:
    output = ""
    for msg in msgs:
        output += msg.user + ": " + msg.content + "\n"
    return output


def msgs2dicts(msgs: list[Message]) -> list[dict]:
    return [msg.to_dict() for msg in msgs]


def execute_msg(msg: Message) -> Generator[Message, None, None]:
    """Uses any tools called in a message and returns the response."""
    assert msg.role == "assistant", "Only assistant messages can be executed"

    for line in msg.content.splitlines():
        yield from _execute_linecmd(line)

    # get all markdown code blocks
    # we support blocks beginning with ```python and ```bash
    codeblocks = [codeblock for codeblock in msg.content.split("```")
                  if codeblock.startswith("python") or codeblock.startswith("bash")]
    for codeblock in codeblocks:
        yield from _execute_codeblock(codeblock)

    yield from _execute_save(msg.content)


def _print_preview():
    # print a preview section header
    print(colored("Preview", "white", attrs=["bold"]))


def _execute_save(text: str, ask=True) -> Generator[Message, None, None]:
    """Saves a codeblock to a file."""
    # last scanned codeblock
    prev_codeblock = ""
    # currently scanning codeblock
    codeblock = ""

    for line in text.splitlines():
        if line.startswith("save:"):
            filename = line.split(":")[1].strip()
            content = "\n".join(prev_codeblock.split("\n")[1:-2])
            _print_preview()
            print(f"# filename: {filename}")
            print(textwrap.indent(content, "> "))
            confirm = input("Save to " + filename + "? (Y/n) ")
            if confirm.lower() in ["y", "Y", "", "yes"]:
                with open(filename, "w") as file:
                    file.write(content)
            yield Message("system", "Saved to " + filename)

        if line.startswith("```") or codeblock:
            codeblock += line + "\n"
            # if block if complete
            if codeblock.startswith("```") and codeblock.strip().endswith("```"):
                prev_codeblock = codeblock
                codeblock = ""


def _execute_load(filename: str) -> Generator[Message, None, None]:
    if not os.path.exists(filename):
        yield Message("system", "Tried to load file '" + filename + "', but it does not exist.")
    confirm = input("Load from " + filename + "? (Y/n) ")
    if confirm.lower() in ["y", "Y", "", "yes"]:
        with open(filename, "r") as file:
            data = file.read()
        yield Message("system", f"# filename: {filename}\n\n{data}")


def _execute_linecmd(line: str) -> Generator[Message, None, None]:
    """Executes a line command and returns the response."""
    if line.startswith("terminal: "):
        cmd = line[len("terminal: "):]
        yield from _execute_shell(cmd)
    elif line.startswith("python: "):
        cmd = line[len("python: "):]
        yield from _execute_python(cmd)
    elif line.startswith("load: "):
        filename = line[len("load: "):]
        yield from _execute_load(filename)


def _execute_codeblock(codeblock: str) -> Generator[Message, None, None]:
    """Executes a codeblock and returns the output."""
    codeblock_lang = codeblock.splitlines()[0].strip()
    codeblock = codeblock[len(codeblock_lang):]
    if codeblock_lang in ["python"]:
        yield from _execute_python(codeblock)
    elif codeblock_lang in ["terminal", "bash"]:
        yield from _execute_shell(codeblock)
    else:
        raise ValueError(f"Unknown codeblock type {codeblock_lang}")


def _execute_shell(cmd: str, ask=True) -> Generator[Message, None, None]:
    """Executes a shell command and returns the output."""
    cmd = cmd.strip()
    if cmd.startswith("$ "):
        cmd = cmd[len("$ "):]
    if ask:
        _print_preview()
        print("$ " + colored(cmd, "light_yellow"))
        confirm = input(colored(f"{EMOJI_WARN} Execute command in terminal? (Y/n) ", "red", "on_light_yellow"))
    if not ask or confirm.lower() in ["y", "Y", "", "yes"]:
        response = os.popen(cmd).read()
        yield Message("system", "```bash\n" + cmd + "\n```\n\nOutput:\n\n```\n" + response.strip() + "\n```")


locals_ = locals()


def _execute_python(code: str, ask=True) -> Generator[Message, None, None]:
    """Executes a python codeblock and returns the output."""
    # TODO: use a persistent python interpreter
    code = code.strip()
    if ask:
        _print_preview()
        print(">>> " + colored(code, "light_yellow"))
        confirm = input(colored(f" {EMOJI_WARN} Execute Python code? (y/N) ", "red", "on_light_yellow", attrs=["bold"]))

    error_during_execution = False
    if not ask or confirm.lower() in ["y", "yes"]:
        # parse code into statements
        import ast
        try:
            statements = ast.parse(code).body
        except SyntaxError as e:
            yield Message("system", f"SyntaxError: {e}")
            return

        output = ""
        # execute statements
        for stmt in statements:
            stmt_str = ast.unparse(stmt)
            output += ">>> " + stmt_str + "\n"
            try:
                # if stmt is assignment or function def, have to use exec
                if isinstance(stmt, ast.Assign) \
                        or isinstance(stmt, ast.FunctionDef) \
                        or isinstance(stmt, ast.Import):
                    exec(stmt_str, globals(), locals_)
                else:
                    result = eval(stmt_str, globals(), locals_)
                    if result is not None:
                        output += str(result) + "\n"
            except Exception as e:
                output += f"{e.__class__.__name__}: {e}\n"
                error_during_execution = True
                break
        if error_during_execution:
            output += "Error during execution, aborting."
        yield Message("system", output)


def test_execute_python():
    assert _execute_python("1 + 1", ask=False) == ">>> 1 + 1\n2\n"
    assert _execute_python("a = 2\na", ask=False) == ">>> a = 2\n>>> a\n2\n"
    assert _execute_python("print(1)", ask=False) == ">>> print(1)\n"


@memory.cache
def _llm_summarize(content: str) -> str:
    """Summarizes a long text using a LLM algorithm."""
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt="Please summarize the following:\n" + content + "\n\nSummary:",
        temperature=0,
        max_tokens=256,
    )
    return response.choices[0].text


def len_tokens(content: str | list[Message]) -> float:
    """Approximate the number of tokens in a string by assuming words have len 4 (lol)."""
    if isinstance(content, list):
        return sum(len_tokens(msg.content) for msg in content)
    return len(content.split(" ")) / 4


def summarize(msg: Message) -> Message:
    """Uses a cheap LLM to summarize long outputs."""
    if len(msg.content) > 2000:
        # first 100 tokens
        beginning = " ".join(msg.content.split()[:150])
        # last 100 tokens
        end = " ".join(msg.content.split()[-100:])
        summary = _llm_summarize(beginning + "\n...\n" + end)
    elif len(msg.content) > 500:
        summary = _llm_summarize(msg.content)
    else:
        # Short enough
        return msg
    logger.info(f"Summarized long output ({len_tokens(msg.content)} tokens): " + summary)
    return Message("system", f"Here is a summary of the response:\n{summary}")


def reduce_log(log: list[Message]) -> Generator[Message, None, None]:
    """Reduces the log to a more manageable size."""
    tokens = 0.
    for msg in log[1:]:
        tokens += len_tokens(msg.content)
        if msg.role == "system":
            if len_tokens(msg.content) > 100:
                msg = summarize(msg)
        yield msg


TOKEN_LIMIT_SOFT = 500
TOKEN_LIMIT_HARD = 500


def limit_log(log: list[Message]) -> list[Message]:
    """
    Picks chat log messages, until the total number of tokens exceeds 2000.
    Walks in reverse order through the log, and picks messages until the total number of tokens exceeds 2000.
    Will always pick the first few system messages.
    """
    tokens = 0.

    # Always pick the first system messages
    initial_system_msgs = []
    for msg in log:
        if msg.role != "system":
            break
        initial_system_msgs.append(msg)
        tokens += len_tokens(msg.content)

    # Pick the last messages until we exceed the token limit
    msgs = []
    for msg in reversed(log[len(initial_system_msgs):]):
        tokens += len_tokens(msg.content)
        if tokens > TOKEN_LIMIT_HARD:
            break
        msgs.append(msg)

    if tokens > TOKEN_LIMIT_SOFT:
        logger.debug(f"Log exceeded {TOKEN_LIMIT_SOFT} tokens")
    return initial_system_msgs + list(reversed(msgs))


role_color = {
    "user": "blue",
    "assistant": "green",
    "system": "light_grey",
}


def print_log(log: Message | list[Message], oneline: bool = True) -> None:
    """Prints the log to the console."""
    for msg in log if isinstance(log, list) else [log]:
        userprefix = colored(msg.user, role_color[msg.role], attrs=["bold"]) + ": "
        # get terminal width
        max_len = shutil.get_terminal_size().columns - len(userprefix)
        output = ""
        if oneline:
            output += textwrap.shorten(msg.content.replace("\n", "\\n"), width=max_len, placeholder="...")
            if len(output) < 20:
                output = msg.content.replace("\n", "\\n")[:max_len] + "..."
        else:
            multiline = len(msg.content.split("\n")) > 1
            output += ("\n  " if multiline else "") + textwrap.indent(msg.content, prefix='  ')[2:]
        output = colored(output, "light_grey")
        print("\n" + userprefix + output.rstrip())


def main():
    """Main interactivity loop."""
    openai.api_key = os.environ["OPENAI_API_KEY"]

    log = read_log()
    print_log(log, oneline=False)
    print("--- ^^^ past messages ^^^ ---")

    # if last message was from assistant, try to run tools again
    if log[-1].role == "assistant":
        for m in execute_msg(log[-1]):
            log.append(m)
            print_log([m], oneline=False)
            write_log(log)

    while True:
        # if last message was from the user (such as from crash/edited log), generate response
        if log[-1].role != "user":
            inquiry = input("> ")
            log.append(Message("user", inquiry))
            write_log(log)

        # if large context, try to reduce/summarize
        reduce = True
        if reduce:
            #print("Reducing log...")
            reduced_log = list(reduce_log(log))
            limited_log = limit_log(reduced_log)
            if len(log) != len(reduced_log):
                print(f"Reduced log from {len_tokens(log)//1} to {len_tokens(reduced_log)//1} tokens")
            if len(log) != len(limited_log):
                print(f"Limited log from {len(log)} to {len(limited_log)} messages")

        # print in-progress indicator
        print(colored("Assistant", "green", attrs=["bold"]) + ": Thinking...", end="\r")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=msgs2dicts(limited_log) if reduce else msgs2dicts(log),
            temperature=0,
        )
        print(" " * shutil.get_terminal_size().columns, end="\r")

        # print response
        msg = Message("assistant", response.choices[0].message.content)
        log.append(msg)
        write_log(log)
        print_log([msg], oneline=False)

        # run tools
        for result_msg in execute_msg(msg):
            log.append(result_msg)
            write_log(log)
            print_log([result_msg], oneline=False)


if __name__ == "__main__":
    main()
