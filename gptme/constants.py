"""
Constants
"""

# Optimized for code
# Discussion here: https://community.openai.com/t/cheat-sheet-mastering-temperature-and-top-p-in-chatgpt-api-a-few-tips-and-tricks-on-controlling-the-creativity-deterministic-output-of-prompt-responses/172683
# TODO: make these configurable

TEMPERATURE = 0
TOP_P = 0.1

# separator for multiple rounds of prompts on the command line
# demarcates the end of the user's prompt, and start of the assistant's response
# e.g. /gptme "generate a poem" "-" "save it to poem.txt"
# where the assistant will generate a poem, and then save it to poem.txt
MULTIPROMPT_SEPARATOR = "-"

# Prompts
ROLE_COLOR = {
    "user": "green",
    "assistant": "green",
    "system": "grey42",
}

PROMPT_USER = f"[bold {ROLE_COLOR['user']}]User[/bold {ROLE_COLOR['user']}]"
PROMPT_ASSISTANT = (
    f"[bold {ROLE_COLOR['assistant']}]Assistant[/bold {ROLE_COLOR['assistant']}]"
)
