from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gptme.eval.main import EvalSpec


def check_output_erik(ctx):
    return "Erik" in ctx.stdout


tests: list["EvalSpec"] = [
    {
        "name": "whois-superuserlabs-ceo",
        "files": {},
        "run": "cat answer.txt",
        "prompt": "who is the CEO of Superuser Labs? write the answer to answer.txt",
        "expect": {
            "correct output": check_output_erik,
        },
    },
]
