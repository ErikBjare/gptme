"""
CLI for gptme utility commands.
"""

import sys
from pathlib import Path

import click

from ..dirs import get_logs_dir
from ..logmanager import LogManager
from ..message import Message
from ..tools.chats import list_chats


@click.group()
def main():
    """Utility commands for gptme."""
    pass


@main.group()
def chats():
    """Commands for managing chat logs."""
    pass


@chats.command("ls")
@click.option("-n", "--limit", default=20, help="Maximum number of chats to show.")
@click.option(
    "--summarize", is_flag=True, help="Generate LLM-based summaries for chats"
)
def chats_list(limit: int, summarize: bool):
    """List conversation logs."""
    if summarize:
        from gptme.init import init  # fmt: skip

        # This isn't the best way to initialize the model for summarization, but it works for now
        init("openai/gpt-4o", interactive=False, tool_allowlist=[])
    list_chats(max_results=limit, include_summary=summarize)


@chats.command("read")
@click.argument("name")
def chats_read(name: str):
    """Read a specific chat log."""

    logdir = Path(get_logs_dir()) / name
    if not logdir.exists():
        print(f"Chat '{name}' not found")
        return

    log = LogManager.load(logdir)
    for msg in log.log:
        if isinstance(msg, Message):
            print(f"{msg.role}: {msg.content}")


@main.group()
def tokens():
    """Commands for token counting."""
    pass


@tokens.command("count")
@click.argument("text", required=False)
@click.option("-m", "--model", default="gpt-4", help="Model to use for token counting.")
@click.option(
    "-f", "--file", type=click.Path(exists=True), help="File to count tokens in."
)
def tokens_count(text: str | None, model: str, file: str | None):
    """Count tokens in text or file."""
    import tiktoken  # fmt: skip

    # Get text from file if specified
    if file:
        with open(file) as f:
            text = f.read()
    elif not text and not sys.stdin.isatty():
        text = sys.stdin.read()

    if not text:
        print("Error: No text provided. Use --file or pipe text to stdin.")
        return

    # Validate model
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        print(f"Error: Model '{model}' not supported by tiktoken.")
        print("Supported models include: gpt-4, gpt-3.5-turbo, text-davinci-003")
        sys.exit(1)

    # Count tokens
    tokens = enc.encode(text)
    print(f"Token count ({model}): {len(tokens)}")


@main.group()
def context():
    """Commands for context generation."""
    pass


@context.command("generate")
@click.argument("path", type=click.Path(exists=True))
def context_generate(_path: str):
    """Generate context from a directory."""
    pass
    # from ..context import generate_context  # fmt: skip

    # ctx = generate_context(path)
    # print(ctx)


@main.group()
def tools():
    """Tool-related utilities."""
    pass


@tools.command("list")
@click.option(
    "--available/--all", default=True, help="Show only available tools or all tools"
)
@click.option("--langtags", is_flag=True, help="Show language tags for code execution")
def tools_list(available: bool, langtags: bool):
    """List available tools."""
    from ..commands import _gen_help  # fmt: skip
    from ..tools import init_tools, loaded_tools  # fmt: skip

    # Initialize tools
    init_tools()

    if langtags:
        # Show language tags using existing help generator
        for line in _gen_help(incl_langtags=True):
            if line.startswith("Supported langtags:"):
                print("\nSupported language tags:")
                continue
            if line.startswith("  - "):
                print(line)
        return

    print("Available tools:")
    for tool in loaded_tools:
        if not available or tool.available:
            status = "✓" if tool.available else "✗"
            print(
                f"""
{status} {tool.name}
   {tool.desc}"""
            )


@tools.command("info")
@click.argument("tool_name")
def tools_info(tool_name: str):
    """Show detailed information about a tool."""
    from ..tools import get_tool, init_tools, loaded_tools  # fmt: skip

    # Initialize tools
    init_tools()

    tool = get_tool(tool_name)
    if not tool:
        print(f"Tool '{tool_name}' not found. Available tools:")
        for t in loaded_tools:
            print(f"- {t.name}")
        sys.exit(1)

    print(f"Tool: {tool.name}")
    print(f"Description: {tool.desc}")
    print(f"Available: {'Yes' if tool.available else 'No'}")
    print("\nInstructions:")
    print(tool.instructions)
    if tool.examples:
        print("\nExamples:")
        print(tool.examples)


if __name__ == "__main__":
    main()
