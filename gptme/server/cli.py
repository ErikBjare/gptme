import logging

import click

from ..init import init, init_logging

logger = logging.getLogger(__name__)


@click.command("gptme-server")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output.")
@click.option(
    "--model",
    default=None,
    help="Model to use by default, can be overridden in each request.",
)
def main(verbose: bool, model: str | None):  # pragma: no cover
    """
    Starts a server and web UI for gptme.

    Note that this is very much a work in progress, and is not yet ready for normal use.
    """
    init_logging(verbose)
    init(model, interactive=False)

    # if flask not installed, ask the user to install `server` extras
    try:
        __import__("flask")
    except ImportError:
        logger.error(
            "gptme installed without needed extras for server. "
            "Install them with `pip install gptme-python[server]`"
        )
        exit(1)
    click.echo("Initialization complete, starting server")

    # noreorder
    from gptme.server.api import main as server_main  # fmt: skip
    server_main()
