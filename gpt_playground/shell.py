"""
Use the OpenAI Chat API to generate shell commands to perform system actions and help develop software.
"""

from copy import copy
import openai

import click

# TODO: Generate automatically
system_info_arch = """
OS: Arch Linux
"""

system_info_macos = """
$ uname -a
Darwin erb-m2.localdomain 21.6.0 Darwin Kernel Version 21.6.0: Sat Jun 18 17:07:28 PDT 2022; root:xnu-8020.140.41~1/RELEASE_ARM64_T8110 arm64 arm Darwin
$ sw_vers
ProductName:	macOS
ProductVersion:	12.5
BuildVersion:	21G72
"""

initial_messages = [
    {
        "role": "system",
        "content": """You are a helpful programming assistant.
You help the user generate shell commands to perform system actions and help develop software.""".strip()
     },
    {
        "role": "system",
        "content": """First, let's check the environment:\n"""  + system_info_macos
    }
]



@click.command()
def main():
    msgs = copy(initial_messages)
    while True:
        query = input(">>> ")
        msgs = ask(query, msgs)
        msg = msgs[-1]
        print(f"[{msg['role']}]: {msg['content']}")


def ask(query: str, msgs=None):
    if msgs is None:
        msgs = copy(initial_messages)

    msgs = msgs + [
        {"role": "user", "content": query}
    ]
    res = openai.Completion.create(
        model="gpt-3.5-turbo",
        messages=msgs
    )
    msg = res['choices'][0]['message']
    msgs = msgs + [msg]
    return msgs

if __name__ == "__main__":
    main()
