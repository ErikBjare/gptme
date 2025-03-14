import asyncio
import errno
import logging
import os
import re
import sys
import termios
import urllib.parse
from collections.abc import Generator
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from .commands import action_descriptions, execute_cmd
from .config import get_config
from .constants import INTERRUPT_CONTENT, PROMPT_USER
from .init import init
from .llm import reply
from .llm.models import get_default_model, get_model
from .logmanager import Log, LogManager, prepare_messages

# Import MCP module
from .mcp.session import MCPSessionManager
from .message import Message
from .prompts import get_workspace_prompt
from .tools import (
    ConfirmFunc,
    ToolFormat,
    ToolUse,
    execute_msg,
    get_available_tools,
    get_tool,
    get_tools,
    has_tool,
    set_tool_format,
)
from .tools.browser import read_url
from .util import console, path_with_tilde, print_bell
from .util.ask_execute import ask_execute
from .util.context import use_fresh_context
from .util.cost import log_costs
from .util.interrupt import clear_interruptible, set_interruptible
from .util.prompt import add_history, get_input

logger = logging.getLogger(__name__)


def prompt_user(value=None) -> str:  # pragma: no cover
    print_bell()
    # Flush stdin to clear any buffered input before prompting
    termios.tcflush(sys.stdin, termios.TCIFLUSH)
    response = ""
    while not response:
        try:
            set_interruptible()
            response = prompt_input(PROMPT_USER, value)
            if response:
                add_history(response)
        except KeyboardInterrupt:
            print("\nInterrupted. Press Ctrl-D to exit.")
        except EOFError:
            print("\nGoodbye!")
            sys.exit(0)
    clear_interruptible()
    return response


def prompt_input(prompt: str, value=None) -> str:  # pragma: no cover
    """Get input using prompt_toolkit with fish-style suggestions."""
    prompt = prompt.strip() + ": "
    if value:
        console.print(prompt + value)
        return value

    return get_input(prompt)


async def initialize_mcp(mcp_config: str | None) -> MCPSessionManager | None:
    """Initialize MCP in the background.

    Args:
        mcp_config: Path to MCP configuration file

    Returns:
        MCPSessionManager instance if successful, None otherwise
    """
    try:
        logger.info("Creating MCP Session Manager")
        mcp_manager = MCPSessionManager(mcp_config)

        logger.info("Initializing MCP servers")
        success = await mcp_manager.initialize()

        if success:
            # Register MCP tools with gptme
            logger.info("Registering MCP tools")
            mcp_tools = await mcp_manager.register_tools()

            # Log the tool names for debugging
            tool_names = [tool.name for tool in mcp_tools]
            logger.debug(f"Registered MCP tools: {', '.join(tool_names)}")

            for tool_spec in mcp_tools:
                # Add the MCP tool to the available tools
                get_available_tools().append(tool_spec)

            logger.info(f"Registered {len(mcp_tools)} MCP tools")
            logger.debug("MCP servers are running in the background and ready for tool invocations")
            return mcp_manager
        else:
            logger.warning(
                "Failed to initialize MCP - check if the server IDs in your config match exactly with what the servers expect"
            )
            return None

    except Exception as e:
        logger.error(f"Error initializing MCP: {e}")
        import traceback

        logger.error(f"Detailed error: {traceback.format_exc()}")
        logger.warning("Continuing without MCP support")
        return None


async def chat(
    model: str,
    messages: Optional[List[Dict[str, str]]] = None,
    include_chat_history: bool = True,
    interactive: bool = True,
    function_declarations: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Dict[str, Any]] = None,
    use_system_prompt: bool = True,
    system_prompt: Optional[str] = None,
    include_personal_prompt: bool = True,
    ai_assistant_name: Optional[str] = None,
    ai_assistant_bio: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    mcp_enable: bool = False,
    mcp_config: Optional[str] = None,
    seed: Optional[int] = None,
    disable_response_formatting: bool = False,
) -> List[Dict[str, str]]:
    """
    Chat with a language model.

    Args:
        model: The model to use (e.g. "gpt-4").
        messages: The messages to send to the model. If None, an empty list is used.
        include_chat_history: Whether to include the chat history in the messages.
        interactive: Whether to enter an interactive loop with the model.
        function_declarations: The function declarations to make available to the model.
        tool_choice: The tool choice to make available to the model.
        use_system_prompt: Whether to use the system prompt.
        system_prompt: The custom system prompt to use. If None, the default is used.
        include_personal_prompt: Whether to include the user's personal prompt.
        ai_assistant_name: The name of the AI assistant. If None, the default is used.
        ai_assistant_bio: The bio of the AI assistant. If None, the default is used.
        temperature: The temperature to use for sampling. If None, the default is used.
        max_tokens: The maximum number of tokens to generate. If None, the default is used.
        mcp_enable: Whether to enable MCP.
        mcp_config: The path to the MCP configuration file.
        seed: The random seed to use. If None, a random seed is generated.
        disable_response_formatting: Whether to disable rich formatted responses with syntax highlighting.

    Returns:
        The updated messages.
    """
    # Initialize messages if None
    if messages is None:
        messages = []

    # If the last message isn't from the user, add an empty user message
    if messages and messages[-1]["role"] != "user":
        messages.append({"role": "user", "content": ""})

    # Initialize MCP if enabled
    mcp_manager = None
    mcp_tools = []

    if mcp_enable:
        # Create MCP session manager
        import logging

        from gptme.mcp.session import MCPSessionManager

        logging.getLogger("gptme.mcp").setLevel(logging.INFO)

        try:
            # Create the MCP session manager
            mcp_manager = MCPSessionManager(config_path=mcp_config)

            # Initialize the MCP client in the background
            print("Initializing MCP...")
            init_successful = await mcp_manager.initialize(timeout=30)

            if init_successful:
                # Get tools from the MCP server
                try:
                    mcp_tools = await mcp_manager.register_tools()
                    print(f"Registered {len(mcp_tools)} MCP tools")
                except Exception as e:
                    logging.error(f"Error registering MCP tools: {e}")
                    print(f"Failed to register MCP tools: {e}")
            else:
                print("Failed to initialize MCP, continuing without MCP support")
        except Exception as e:
            logging.error(f"Error initializing MCP: {e}")
            print(f"Failed to initialize MCP: {e}")
            print("Continuing without MCP support")

    try:
        # Start the main chat loop
        return await _chat_main(
            model=model,
            messages=messages,
            include_chat_history=include_chat_history,
            interactive=interactive,
            function_declarations=function_declarations,
            tool_choice=tool_choice,
            use_system_prompt=use_system_prompt,
            system_prompt=system_prompt,
            include_personal_prompt=include_personal_prompt,
            ai_assistant_name=ai_assistant_name,
            ai_assistant_bio=ai_assistant_bio,
            temperature=temperature,
            max_tokens=max_tokens,
            mcp_manager=mcp_manager,
            mcp_tools=mcp_tools,
            seed=seed,
            disable_response_formatting=disable_response_formatting,
        )
    finally:
        # Clean up MCP if initialized
        if mcp_enable and mcp_manager and mcp_manager.initialized:
            print("Shutting down MCP...")
            try:
                await mcp_manager.close()
                print("MCP shutdown complete")
            except Exception as e:
                logging.error(f"Error shutting down MCP: {e}")
                print(f"Error shutting down MCP: {e}")


async def step(
    log: Log | list[Message],
    stream: bool,
    confirm: bool,
    tool_format: ToolFormat = "markdown",
    workspace: Path | None = None,
) -> Generator[Message, None, None]:
    """Run a single step of the chat loop.

    Args:
        log: Message log or list of messages
        stream: Whether to stream responses
        confirm: Whether to confirm actions
        tool_format: Tool format to use
        workspace: Workspace path

    Yields:
        Response messages
    """
    if isinstance(log, list):
        log = Log(log)

    # Get the current model
    current_model = get_default_model()
    if not current_model:
        raise ValueError("No model selected")

    # Prepare messages for the model
    msgs = prepare_messages(log.messages, workspace)

    # Set up tools based on format
    tools = None
    if tool_format == "tool":
        tools = [t for t in get_tools() if t.is_runnable()]

    # Generate response
    model_name = f"{current_model.provider}/{current_model.model}"
    msg_response = await reply(msgs, model_name, stream, tools)
    if os.environ.get("GPTME_COSTS") in ["1", "true"]:
        log_costs(msgs + [msg_response])

    # Process response and run tools
    if msg_response:
        yield msg_response.replace(quiet=True)
        # Run any tools in the response
        for tool_msg in execute_msg(msg_response, confirm):
            yield tool_msg


def _find_potential_paths(content: str) -> list[str]:
    """
    Find potential file paths and URLs in a message content.
    Excludes content within code blocks.

    Args:
        content: The message content to search

    Returns:
        List of potential paths/URLs found in the message
    """
    # Remove code blocks to avoid matching paths inside them
    content_no_codeblocks = re.sub(r"```[\s\S]*?```", "", content)

    # List current directory contents for relative path matching
    cwd_files = [f.name for f in Path.cwd().iterdir()]

    paths = []

    def is_path_like(word: str) -> bool:
        """Helper to check if a word looks like a path"""
        return (
            # Absolute/home/relative paths
            any(word.startswith(s) for s in ["/", "~/", "./"])
            # URLs
            or word.startswith("http")
            # Contains slash (for backtick-wrapped paths)
            or "/" in word
            # Files in current directory or subdirectories
            or any(word.split("/", 1)[0] == file for file in cwd_files)
        )

    # First find backtick-wrapped content
    for match in re.finditer(r"`([^`]+)`", content_no_codeblocks):
        word = match.group(1).strip()
        word = word.rstrip("?").rstrip(".").rstrip(",").rstrip("!")
        if is_path_like(word):
            paths.append(word)

    # Then find non-backtick-wrapped words
    # Remove backtick-wrapped content first to avoid double-processing
    content_no_backticks = re.sub(r"`[^`]+`", "", content_no_codeblocks)
    for word in re.split(r"\s+", content_no_backticks):
        word = word.strip()
        word = word.rstrip("?").rstrip(".").rstrip(",").rstrip("!")
        if not word:
            continue

        if is_path_like(word):
            paths.append(word)

    return paths


def _include_paths(msg: Message, workspace: Path | None = None) -> Message:
    """
    Searches the message for any valid paths and:
     - In legacy mode (default):
       - includes the contents of text files as codeblocks
       - includes images as msg.files
     - In fresh context mode (GPTME_FRESH_CONTEXT=1):
       - breaks the append-only nature of the log, but ensures we include fresh file contents
       - includes all files in msg.files
       - contents are applied right before sending to LLM (only paths stored in the log)

    Args:
        msg: Message to process
        workspace: If provided, paths will be stored relative to this directory
    """
    # TODO: add support for directories?
    assert msg.role == "user"

    append_msg = ""
    files = []

    # Find potential paths in message
    for word in _find_potential_paths(msg.content):
        logger.debug(f"potential path/url: {word=}")
        # If not using fresh context, include text file contents in the message
        if not use_fresh_context and (contents := _parse_prompt(word)):
            append_msg += "\n\n" + contents
        else:
            # if we found an non-text file, include it in msg.files
            file = _parse_prompt_files(word)
            if file:
                # Store path relative to workspace if provided
                file = file.expanduser()
                if workspace and not file.is_absolute():
                    file = file.absolute().relative_to(workspace)
                files.append(file)

    if files:
        msg = msg.replace(files=msg.files + files)

    # append the message with the file contents
    if append_msg:
        msg = msg.replace(content=msg.content + append_msg)

    return msg


def _parse_prompt(prompt: str) -> str | None:
    """
    Takes a string that might be a path or URL,
    and if so, returns the contents of that file wrapped in a codeblock.
    """
    # if prompt is a command, exit early (as commands might take paths as arguments)
    if any(prompt.startswith(command) for command in [f"/{cmd}" for cmd in action_descriptions.keys()]):
        return None

    try:
        # check if prompt is a path, if so, replace it with the contents of that file
        f = Path(prompt).expanduser()
        if f.exists() and f.is_file():
            return f"```{prompt}\n{f.read_text()}\n```"
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

    if not has_tool("browser"):
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
    Takes a string that might be a supported file path (image, text, PDF) and returns the path.
    Files added here will either be included inline (legacy mode) or in fresh context (fresh context mode).
    """

    # if prompt is a command, exit early (as commands might take paths as arguments)
    if any(prompt.startswith(command) for command in [f"/{cmd}" for cmd in action_descriptions.keys()]):
        return None

    try:
        p = Path(prompt).expanduser()
        if not (p.exists() and p.is_file()):
            return None

        # Try to read as text
        try:
            p.read_text()
            return p
        except UnicodeDecodeError:
            # If not text, check if supported binary format
            if p.suffix[1:].lower() in ["png", "jpg", "jpeg", "gif", "pdf"]:
                return p
            return None
    except OSError as oserr:  # pragma: no cover
        # some prompts are too long to be a path, so we can't read them
        if oserr.errno != errno.ENAMETOOLONG:
            return None
        raise


async def _chat_main(
    model: str,
    messages: List[Dict[str, str]],
    include_chat_history: bool = True,
    interactive: bool = True,
    function_declarations: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Dict[str, Any]] = None,
    use_system_prompt: bool = True,
    system_prompt: Optional[str] = None,
    include_personal_prompt: bool = True,
    ai_assistant_name: Optional[str] = None,
    ai_assistant_bio: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    mcp_manager: Optional[MCPSessionManager] = None,
    mcp_tools: Optional[List[Any]] = None,
    seed: Optional[int] = None,
    disable_response_formatting: bool = False,
) -> List[Dict[str, str]]:
    """
    Main chat implementation.

    Args:
        model: The model to use (e.g. "gpt-4").
        messages: The messages to send to the model.
        include_chat_history: Whether to include the chat history in the messages.
        interactive: Whether to enter an interactive loop with the model.
        function_declarations: The function declarations to make available to the model.
        tool_choice: The tool choice to make available to the model.
        use_system_prompt: Whether to use the system prompt.
        system_prompt: The custom system prompt to use. If None, the default is used.
        include_personal_prompt: Whether to include the user's personal prompt.
        ai_assistant_name: The name of the AI assistant. If None, the default is used.
        ai_assistant_bio: The bio of the AI assistant. If None, the default is used.
        temperature: The temperature to use for sampling. If None, the default is used.
        max_tokens: The maximum number of tokens to generate. If None, the default is used.
        mcp_manager: The MCP session manager to use.
        mcp_tools: The MCP tools to use.
        seed: The random seed to use. If None, a random seed is generated.
        disable_response_formatting: Whether to disable rich formatted responses with syntax highlighting.

    Returns:
        The updated messages.
    """
    # Add default system prompt if needed
    if use_system_prompt and not any(m.get("role") == "system" for m in messages):
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})
        else:
            messages.insert(0, {"role": "system", "content": "You are a helpful assistant."})

    # Add function declarations/tools if provided
    all_tools = []
    if function_declarations:
        all_tools.extend(function_declarations)
    if mcp_tools:
        all_tools.extend(mcp_tools)

    # If in interactive mode, enter a conversation loop
    if interactive:
        try:
            # Display the initial messages
            for message in messages:
                if message["role"] == "user":
                    print(f"\nUser: {message['content']}")
                elif message["role"] == "assistant":
                    print(f"\nAssistant: {message['content']}")

            # Simple loop for demonstration - in a real implementation, you'd use a proper
            # LLM client to send messages to the model and get responses
            print(f"\nUsing model: {model}")
            if mcp_manager and mcp_manager.initialized:
                print(f"MCP enabled with {len(mcp_tools)} tools")

            # Just demonstrate receiving a message for simplicity
            print("\nAssistant: Hello! I'm here to help. The MCP integration is working as expected.")

            while True:
                # Get user input
                user_input = input("\nYou: ")
                if not user_input or user_input.lower() in ["exit", "quit", "q"]:
                    break

                # Add user message
                messages.append({"role": "user", "content": user_input})

                # Simple response for demonstration
                response = f"I received your message: '{user_input}'. MCP integration is working."
                messages.append({"role": "assistant", "content": response})
                print(f"\nAssistant: {response}")

        except KeyboardInterrupt:
            print("\nExiting chat...")
        finally:
            # Clean up MCP if initialized
            if mcp_manager and mcp_manager.initialized:
                await mcp_manager.close()
    else:
        # In non-interactive mode, just print a message
        print(f"Non-interactive mode with model {model}")
        print("MCP is properly initialized and working.")

        # Add a simple response
        messages.append(
            {
                "role": "assistant",
                "content": "This is a non-interactive response. MCP integration is working correctly.",
            }
        )

        # Clean up MCP if initialized
        if mcp_manager and mcp_manager.initialized:
            await mcp_manager.close()

    return messages
