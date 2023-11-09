# prefix for commands, e.g. /help
CMDFIX = "/"

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

# colors wrapped in \001 and \002 to inform readline about non-printable characters
PROMPT_USER = (
    f"\001[bold {ROLE_COLOR['user']}]\002User\001[/bold {ROLE_COLOR['user']}]\002"
)
PROMPT_ASSISTANT = (
    f"[bold {ROLE_COLOR['assistant']}]Assistant[/bold {ROLE_COLOR['assistant']}]"
)
