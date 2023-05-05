import json
import shutil
import textwrap

from termcolor import colored

from .message import Message
from .util import len_tokens
from .constants import role_color
from .prompts import initial_prompt
from .reduce import reduce_log, limit_log

class LogManager(list[Message]):
    def __init__(self, log: list[Message] | None = None, logfile: str | None = None):
        self.log = log or []
        assert logfile is not None, "logfile must be specified"
        self.logfile = logfile

    def append(self, msg: Message, quiet=False) -> None:
        """Appends a message to the log, writes the log, prints the message."""
        self.log.append(msg)
        self.write()
        if not quiet:
            self.print()

    def write(self) -> None:
        """Writes the log to the logfile."""
        write_log(self.log, self.logfile)

    def print(self):
        print_log(self.log, oneline=False)

    def undo(self):
        """Removes the last message from the log."""
        undid = None
        assert self.log.pop().content == ".undo"
        print(colored("Undoing messages:", "yellow"))
        while undid is None or undid.role in ["system", "assistant"] or undid.content == ".undo":
            undid = self.log.pop()
            print(colored(f"  {undid.role}: {undid.content[:30]}...", "yellow"))


    def prepare_messages(self) -> list[Message]:
        """Prepares the log into messages before sending it to the LLM."""
        msgs = self.log
        msgs_reduced = list(reduce_log(msgs))
        if len(msgs) != len(msgs_reduced):
            print(
                f"Reduced log from {len_tokens(msgs)//1} to {len_tokens(msgs_reduced)//1} tokens"
            )
        msgs_limited = limit_log(msgs_reduced)
        if len(msgs_reduced) != len(msgs_limited):
            print(f"Limited log from {len(msgs_reduced)} to {len(msgs_limited)} messages")
        return msgs_limited

    @classmethod
    def load(cls, logfile=None) -> 'LogManager':
        """Loads a conversation log."""
        with open(logfile, "r") as file:
            msgs = [Message(**json.loads(line)) for line in file.readlines()]
        if not msgs:
            msgs = initial_prompt()
        return cls(msgs, logfile=logfile)


def write_log(msg_or_log: Message | list[Message], logfile) -> None:
    """
    Writes to the conversation log.
    If a single message given, append.
    If a list of messages given, overwrite.
    """
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
        raise TypeError(
            "Expected Message or list of Messages, got " + str(type(msg_or_log))
        )



def print_log(log: Message | list[Message], oneline: bool = True) -> None:
    """Prints the log to the console."""
    for msg in log if isinstance(log, list) else [log]:
        userprefix = colored(msg.user, role_color[msg.role], attrs=["bold"]) + ": "
        # get terminal width
        max_len = shutil.get_terminal_size().columns - len(userprefix)
        output = ""
        if oneline:
            output += textwrap.shorten(
                msg.content.replace("\n", "\\n"), width=max_len, placeholder="..."
            )
            if len(output) < 20:
                output = msg.content.replace("\n", "\\n")[:max_len] + "..."
        else:
            multiline = len(msg.content.split("\n")) > 1
            output += ("\n  " if multiline else "") + textwrap.indent(
                msg.content, prefix="  "
            )[2:]
        output = colored(output, "light_grey")
        print("\n" + userprefix + output.rstrip())
