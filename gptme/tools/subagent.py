"""
A subagent tool for gptme

Lets gptme break down a task into smaller parts, and delegate them to subagents.
"""


def subagent(prompt: str):
    """Runs a subagent and returns the resulting JSON output."""
    # noreorder
    from gptme import chat  # fmt: skip

    chat("Hello! I am a subagent.")
