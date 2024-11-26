#!/usr/bin/env python3
"""
CLI entry point for running gptme as an MCP server.
"""

import asyncio
import click
import logging
from pathlib import Path

from . import run_server


@click.command()
@click.option(
    "-w",
    "--workspace",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to workspace directory",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Enable verbose logging",
)
def main(workspace: Path | None, verbose: bool):
    """Run gptme as an MCP server.

    This allows other applications to use gptme's capabilities through the Model Context Protocol.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level)

    try:
        asyncio.run(run_server(workspace))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()
