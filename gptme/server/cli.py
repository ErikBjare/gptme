import logging

import click

from ..init import init, init_logging
from .api import create_app

logger = logging.getLogger(__name__)


@click.command("gptme-server")
@click.option("--debug", is_flag=True, help="Debug mode")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option(
    "--model",
    default=None,
    help="Model to use by default, can be overridden in each request.",
)
def main(debug: bool, verbose: bool, model: str | None):  # pragma: no cover
    """
    Starts a server and web UI for gptme.

    Note that this is very much a work in progress, and is not yet ready for normal use.
    """
    init_logging(verbose)
    init(model, interactive=False, tool_allowlist=None)

    # if flask not installed, ask the user to install `server` extras
    try:
        __import__("flask")
    except ImportError:
        logger.error(
            "gptme installed without needed extras for server. "
            "Install them with `pip install gptme[server]`"
        )
        exit(1)
    click.echo("Initialization complete, starting server")

    app = create_app()
    app.run(debug=debug)
