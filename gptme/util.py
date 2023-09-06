import random
from datetime import datetime, timedelta

from rich import print
from rich.console import Console
from rich.syntax import Syntax

from .message import Message

EMOJI_WARN = "⚠️"


def len_tokens(content: str | list[Message]) -> float:
    """Approximate the number of tokens in a string by assuming words have len 4 (lol)."""
    if isinstance(content, list):
        return sum(len_tokens(msg.content) for msg in content)
    return len(content.split(" ")) / 4


def msgs2text(msgs: list[Message]) -> str:
    output = ""
    for msg in msgs:
        output += f"{msg.user}: {msg.content}\n"
    return output


def msgs2dicts(msgs: list[Message]) -> list[dict]:
    return [msg.to_dict() for msg in msgs]


def generate_unique_name():
    actions = [
        "running",
        "jumping",
        "walking",
        "skipping",
        "hopping",
        "flying",
        "swimming",
        "crawling",
        "sneaking",
        "sprinting",
    ]
    adjectives = [
        "funny",
        "red",
        "happy",
        "sad",
        "angry",
        "silly",
        "crazy",
        "sneaky",
        "sleepy",
        "hungry",
    ]
    nouns = [
        "walrus",
        "pelican",
        "cat",
        "dog",
        "elephant",
        "rat",
        "mouse",
        "bird",
        "fish",
        "dragon",
        "unicorn",
        "dinosaur",
    ]

    action = random.choice(actions)
    adjective = random.choice(adjectives)
    noun = random.choice(nouns)
    unique_name = f"{action}-{adjective}-{noun}"
    return unique_name


def epoch_to_age(epoch):
    # takes epoch and returns "x minutes ago", "3 hours ago", "yesterday", etc.
    age = datetime.now() - datetime.fromtimestamp(epoch)
    if age < timedelta(minutes=1):
        return "just now"
    elif age < timedelta(hours=1):
        return f"{age.seconds // 60} minutes ago"
    elif age < timedelta(days=1):
        return f"{age.seconds // 3600} hours ago"
    elif age < timedelta(days=2):
        return "yesterday"
    else:
        return f"{age.days} days ago ({datetime.fromtimestamp(epoch).strftime('%Y-%m-%d')})"


def print_preview(code=None, lang=None):
    # print a preview section header
    print()
    print("[bold white]Preview[/bold white]")
    if code:
        print(Syntax(code.strip(), lang))
        print()


def ask_execute(default=True) -> bool:
    # TODO: add a way to outsource ask_execute decision to another agent/LLM
    console = Console()
    choicestr = f"({'Y' if default else 'y'}/{'n' if default else 'N'})"
    # answer = None
    # while not answer or answer.lower() not in ["y", "yes", "n", "no", ""]:
    answer = console.input(
        f"[bold yellow on red] {EMOJI_WARN} Execute code? {choicestr} [/] ",
    )
    return answer.lower() in (["y", "yes"] + [""] if default else [])
